# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_http_methods

from .forms import LoginForm, UploadFileForm

import csv
import json
from datetime import datetime
from datetime import timedelta

from .models import Trips, Points
from django.db import transaction
from django.contrib.gis.geos import LineString, Point

from geopy.geocoders import Nominatim
from time import sleep
from geopy.exc import GeocoderTimedOut
from geopy.distance import vincenty

# Create your views here.


#####
#####  WEBPAGE SERVING FUNCTIONS
#####

#INDEX.HTML
@require_http_methods(["GET"])
def index(request):
	userform = LoginForm()
	return render (request, 'behaviour/index.html', {'userform': userform})

#MAPOSM.HTML
@require_http_methods(["GET"])
def maposm(request):
	userform = LoginForm()
	return render (request, 'behaviour/maposm.html', {'userform': userform})

#UPLOAD.HTML
def upload(request):
	if request.method == 'POST':
		formupload = UploadFileForm(request.POST, request.FILES)
		if formupload.is_valid():

			npoints = save_points(request.FILES['file'])
			if (npoints == 0):
				messages.error(request, 'This file can not be processed!')
				return HttpResponseRedirect('upload.html')
			else:
				messages.success(request,"Points Saved Correctly")
				return HttpResponseRedirect('maposm.html')

		else:
			messages.error(request,"Error Uploading the File")
			return HttpResponseRedirect('upload.html')
	else:
		userform = LoginForm()
		formupload = UploadFileForm()
		return render(request, 'behaviour/upload.html', {'formupload': formupload, 'userform': userform})


#DISPLAY.HTML
@require_http_methods(["GET"])
def display(request):
	userform = LoginForm()
	update_accelerations()
	return render (request, 'behaviour/display.html', {'userform': userform})


@require_http_methods(["GET"])
def user_logout(request): 
	logout(request)
	messages.add_message(request, messages.SUCCESS, 'You have successfully loged out!')
	return HttpResponseRedirect('/')

@require_http_methods(["GET"])
def downloadfile(request):
	# Create the HttpResponse object with the appropriate CSV header.
	response = HttpResponse(content_type='text/csv')
	response['Content-Disposition'] = 'attachment; filename="data.csv"'

	writer = csv.writer(response)

	tripslist = Trips.objects.values_list('id', 'firsttimestamp', 'city', 'country', 'citytype', 'duration', 'distance', 'velocity', 'npoints', 'naccelerations', 'nbreaks')

	writer.writerow(["tripid", "firsttimestamp", "city", "country", "citytype", "duration", "distance", "velocity", "npoints", "naccelerations", "nbreaks"])	
	for tripid, firsttimestamp, city, country, citytype, duration, distance, velocity, npoints, naccelerations, nbreaks in tripslist:

		writer.writerow([tripid, firsttimestamp, city.encode('utf-8').strip(), country.encode('utf-8').strip(), citytype, duration, distance, velocity, npoints, naccelerations, nbreaks])
		


	return response





#####
#####  BUTTON FUNCTIONS
#####


# When the file is uploaded to the server
# Process the file
# Format input: 
#  	dateTime device_id id latitude longitude speed
#  	2017-01-24T09:49:24.063Z za0 c3e0b6fcd96d0a329903887ec39cb5835780db17 40.42951587 -3.64513278 0
#
# Format in the model:
# 	Points = 	[
#					[timestamp] 			[device_id]	[latitude]		[longitude] 	[speed] [hasTrip]
#					[2017-01-24 09:49:24] 	[za0] 		[40.4251587] 	[-3.64513278] 	[0]		[False]
# 				]
# 
def save_points(file):
	spacer = " "
	print("Saving the points of the file...")

	reader = csv.reader(file, delimiter=str(spacer))

	firstline = file.readline()

	type1 = "dateTime device_id id latitude longitude speed\n"
	type2 = "deviceId,latitude,longitude,dateTime,speed,id\n"

	#print("fl:"+firstline+".")

	ntype=0
	if(firstline[:45] == type1[:45]):
		#print "type1"
		ntype=1
		reader = csv.reader(file, delimiter=str(spacer))
	elif(firstline[:45] == type2[:45]):
		#print "type2"
		ntype=2
		reader = csv.reader(file, delimiter=str(','))
	else:
		print "ERROR: notype"
		print(firstline[:45] + " != " + type1[:45] + " OR " + type2[:45])
		return 0
	counter = 0
	
	with transaction.atomic():
		#for line in file:
		for line in reader:
			#Check the line
			try:
				if(ntype == 1):

					# 2017-02-02T19:18:36.063Z timestamp.strftime("%Y-%m-%d %H:%M:%S")
					timestamp = datetime.strptime(line[0], '%Y-%m-%dT%H:%M:%S.%fZ')
					device_id = line[1]
					latitude = line[3]
					longitude = line[4]
					speed = line[5]
					hastrip = False

					insert = Points(timestamp=timestamp,device_id=device_id,latitude=latitude,longitude=longitude,speed=speed,hasTrip=hastrip)
					insert.save()
					counter+=1

					
				elif(ntype == 2):
					
					# 2017-02-02 19:18:36 timestamp.strftime("%Y-%m-%d %H:%M:%S")
					timestamp = datetime.strptime(line[3][:19], '%Y-%m-%d %H:%M:%S')
					device_id = line[0]
					latitude = line[1]
					longitude = line[2]
					speed = line[4]
					hastrip = False

					insert = Points(timestamp=timestamp,device_id=device_id,latitude=latitude,longitude=longitude,speed=speed,hasTrip=hastrip)
					insert.save()
					counter+=1

			except ValueError:
				# 2017-01-24
				#datetime1 = datetime.strptime(line[0], '%Y-%m-%d')
				print "ValueError: " + str(line)
				continue
			except IndexError:
				print "IndexError: " + str(line)
				continue

	print("Clean Finish, "+str(counter)+" records saved.")

	return counter


# Load trips from the DDBB
def load_trips(request):
	print("Getting positions...")

	gaptime = 120
	gapdistance = 10000 # in meters

	pointsqs = get_points()

	# IF is not empty
	if(pointsqs.exists()):

		ntrips = create_trips(request,pointsqs,gaptime,gapdistance)
		print("Number of trips loaded: "+str(ntrips))
		
		if(ntrips == 0):
			messages.error(request, 'No trips to be processed!')
			return HttpResponseRedirect('maposm.html')
		else:
			messages.success(request,"Trips Generated Correctly")
			return HttpResponseRedirect('maposm.html')

	else:
		messages.error(request, 'No points to be processed!')
		returnHttpResponseRedirect('maposm.html')


# from a queryset with points create a list of points for each trip
# this list will be send to the save_trip function to save in the model each trip (making all the calculations there)
# output list for each trip:
# trip = 	[
#				[id (of the point) ] [timestamp] [device_id] [latitude] [longitude] [speed] 
#			]
def create_trips(request,pointsqs,gaptime,gapdistance):
	print("Creating trips...")

	ntrips = 0
	insertedtrips = 0

	trip = []
	
	#Control if the point is the last point of a list of linked points
	isLastPoint = 0

	iterator = pointsqs.values_list('id','timestamp','device_id','latitude','longitude','speed').iterator()

	# Everything in the same transaction
	with transaction.atomic():

		for prevpoint,thispoint,nextpoint in neighborhood(iterator):
			try:

				thisdate = thispoint[1]
				nextdate = nextpoint[1]
				thisdevice = thispoint[2]
				nextdevice = nextpoint[2]

				distance = vincenty( (thispoint[3],thispoint[4]), (nextpoint[3],nextpoint[4]) ).meters

				# If the time is close, is part of a trip
				if (timedifference(nextdate,thisdate)<timedelta(seconds=gaptime) and thisdevice == nextdevice and distance <=gapdistance):

					#print(thisdevice +" = "+nextdevice)
					#List of points for trip [id][timestamp][device_id][latitud][longitude]
					point = []
					point.append(thispoint[0]) # id (of the point)
					point.append(thispoint[1]) # timestamp
					point.append(thispoint[2]) # device_id
					point.append(thispoint[3]) # latitude
					point.append(thispoint[4]) # longitude
					point.append(thispoint[5]) # speed

					trip.append(point)

					isLastPoint=1

				else:


					# Include the last point to the trip
					if(isLastPoint):
						#List of points for trip [id][timestamp][device_id][latitud][longitude]
						point = []
						point.append(thispoint[0]) # id (of the point)
						point.append(thispoint[1]) # timestamp
						point.append(thispoint[2]) # device_id
						point.append(thispoint[3]) # latitude
						point.append(thispoint[4]) # longitude
						point.append(thispoint[5]) # speed

						trip.append(point)
											
						isLastPoint=0
						# Save or print an error
						if(save_trip(request,trip) == 0):
							print("ERROR: The trip can not be saved")
						else:
							ntrips+=1	
						trip=[]
					


			# Last point of the list
			except StopIteration:
				continue
			except TypeError:
				continue

	return ntrips



#####
#####  UTILITY CLASSES
#####
class geoposition():

	city = None
	citytype = None
	country = None
	state = None

	def __init__(self, latitude, longitude):

		locjson = None
		try:
			sleep(1) # The API need at least 1 sec between each query
			geolocator = Nominatim()
			location = geolocator.reverse(str(latitude) + ", "+ str(longitude))
			locjson = json.loads(json.dumps(location.raw))
			self.city = locjson['address']['city']
			self.citytype="city"
		except GeocoderTimedOut:
			print("Error: Geocode time out")
		except KeyError:
			try:
				self.city = locjson['address']['town']
				self.citytype="town"
			except KeyError:
				try:
					self.city = locjson['address']['village']
					self.citytype="village"
				except KeyError:
					try:
						self.city = locjson['address']['neighbourhood']
						self.citytype="neighbourhood"
					except KeyError:
						try:
							self.city = locjson['address']['hamlet']
							self.citytype="hamlet"
						except KeyError:
							#print(locjson)
							self.city = "Unknown"
							self.citytype="Unknown"
		except Exception as e:
			print("ERROR: " + str(e))
		try:
			self.country = locjson['address']['country']
		except KeyError:
			self.country = "Unknown"
		try:
			self.state = locjson['address']['state']
		except KeyError:
			self.state = "Unknown"



#####
#####  UTILITY FUNCTIONS
#####

# Get the previous, the current and the next item with the iterable
# Usage:
# 		for prev,item,next in neighborhood(l):
#       	print prev, item, next
#
def neighborhood(iterable):
	iterator = iter(iterable)
	prev_item = None
	current_item = next(iterator)  # throws StopIteration if empty.
	for next_item in iterator:
		yield (prev_item, current_item, next_item)
		prev_item = current_item
		current_item = next_item
	yield (prev_item, current_item, None)


# Returns the deltatime between two datatimes
def timedifference(t1,t2):
	if(t1<t2):
		return t2-t1
	else:
		return t1-t2


#####
#####  DDBB FUNCTIONS
#####

# [timestamp, device_id, latitude, longitude, speed]
def insert_points(positions):
	with transaction.atomic():
		for pos in positions:
			insert = Points(timestamp=pos[0],device_id=pos[1],latitude=pos[2],longitude=pos[3],speed=pos[4])
			insert.save()

def delete_points(request):
	Points.objects.all().delete()
	print("All Points Deleted!")
	return HttpResponseRedirect('maposm.html')



# Save the trip in the model
# Trip is a list of points: [id][timestamp][device_id][latitude][longitude][speed]
def save_trip(request,trip):
	#print("Saving trip...")

	if(len(trip) == 0):
		print("ERROR: List Empty!")
		return 0
	
	# Get the first and last points
	firstpoint = trip[0]
	lastpoint = trip[-1]

	username = request.user
	device_id = firstpoint[2]
	firsttimestamp = firstpoint[1]
	lasttimestamp = lastpoint[1]
	firstpointlatitude = firstpoint[3]
	firstpointlongitude = firstpoint[4]
	lastpointlatitude = lastpoint[3]
	lastpointlongitude = lastpoint[4]

	#Create the Geom (list of points)
	listpoints = []
	for p in trip:
		point = Point(float(p[4]),float(p[3])) # (longitude,latitude)
		listpoints.append(point)



	duration = timedifference(firsttimestamp,lasttimestamp).total_seconds()
	distance = vincenty( (firstpointlatitude,firstpointlongitude), (lastpointlatitude,lastpointlongitude) ).meters
	npoints = len(listpoints)

	# no inserts
	if(npoints < 2):
		print("ERROR: Points less than 2!")
		return 0
	if(distance == 0 or duration == 0):
		print("ERROR: Distance or duration is 0")
		return 0

	try:
		velocity = (3.6)*(distance/duration)
	except ZeroDivisionError:
		print("ERROR: Zero Division, duration is zero")
		velocity = 0


	#Determine accelerations
	gapac = 1.5
	gapbk = 0.5
	naccelerations = 0
	nbreaks = 0
	prevspeed=float(trip[0][5])
	for completepoint in trip:

		curspeed = float(completepoint[5])

		# Lecture error? or first/last point?
		if(curspeed !=0 and prevspeed !=0):
			if(prevspeed*gapac < curspeed):
				naccelerations+=1

			if(prevspeed*gapbk > curspeed):
				nbreaks+= 1

		prevspeed=curspeed


	firstposition = geoposition(firstpoint[3],firstpoint[4])
	city = firstposition.city
	country = firstposition.country
	citytype = firstposition.citytype
	state = firstposition.state

	print("Adding: "+ device_id + " Points: " + str(npoints) + " A("+str(naccelerations) +") "+ " B("+str(nbreaks) +") "+" city: " + city + "("+state+")"+"["+country+"]")
	
	insert = Trips( username=username, device_id=device_id,
		firsttimestamp=firsttimestamp, lasttimestamp=lasttimestamp,
		firstpointlatitude=firstpointlatitude, firstpointlongitude=firstpointlongitude,
		lastpointlatitude=lastpointlatitude, lastpointlongitude=firstpointlongitude,
		geom=LineString(listpoints),
		city=city, country=country,citytype=citytype,state=state,
		duration=duration, distance=distance, velocity=velocity, npoints=npoints,
		naccelerations=naccelerations,nbreaks=nbreaks
	)

	insert.save()

	set_points_used(trip)

	return 1



# Return all the points that have not been asociated to a trip
# Ordered by device_id and timestamp
def get_points():

	qs = Points.objects.filter(hasTrip=False).order_by('device_id','timestamp')
	#qs = Points.objects.filter(hasTrip=False,device_id="b10").order_by('device_id','timestamp')

	print("Number of points to be analized: "+str(qs.count()))

	return qs


# Delete all the trips and set all the points availables to calculate trips
def clean_DDBB(request):
	Trips.objects.all().delete()
	set_all_points_noused()
	print("All Data Deleted!")
	return HttpResponseRedirect('maposm.html')

# Set true to the hasTrip atribute all the points in the list trips
# id is value 0
def set_points_used(trips):

	for p in trips:
		Points.objects.filter(id=p[0]).update(hasTrip=True)

# Set all the points available for creating trips
def set_all_points_noused():
	Points.objects.all().update(hasTrip=False)