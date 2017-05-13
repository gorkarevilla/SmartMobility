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
def clean_DDBB(request):
	Trips.objects.all().delete()
	set_all_points_noused()
	print("All Data Deleted!")
	return HttpResponseRedirect('maposm.html')

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
	pointsqs = get_points()

	# IF is not empty
	if(pointsqs.exists()):

		ntrips = create_trips(request,pointsqs,gaptime)

		if(ntrips == 0):
			messages.error(request, 'No trips to be processed!')
			return HttpResponseRedirect('maposm.html')
		else:
			print("Number of trips loaded: "+str(ntrips))
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
def create_trips(request,pointsqs,gaptime):
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

				#thispoint = p
				#nextpoint = next(iterator)
				#nextpoint = iterator[iterator.index(p)+1]
				#print("This: "+str(thispoint[0]) +" - Next: " +str(nextpoint[0]))

				thisdate = thispoint[1]
				nextdate = nextpoint[1]
				thisdevice = thispoint[2]
				nextdevice = nextpoint[2]

				# If the time is close, is part of a trip
				if (timedifference(nextdate,thisdate)<timedelta(seconds=gaptime) and thisdevice == nextdevice):

					print(thisdevice +" = "+nextdevice)
					#List of points for trip [id][timestamp][device_id][latitud][longitude]
					point = []
					point.append(thispoint[0]) # id (of the point)
					point.append(thispoint[1]) # timestamp
					point.append(thispoint[2]) # device_id
					point.append(thispoint[3]) # latitude
					point.append(thispoint[4]) # longitude
					point.append(thispoint[5]) # speed

					trip.append(point)
					set_point_used(thispoint[0])

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
						set_point_used(thispoint[0])					
						ntrips+=1
						isLastPoint=0
						# Save or print an error
						if(save_trip(request,trip) == 0):
							print("ERROR: One Trip can not be saved")
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
	print("Saving trip...")

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

	print("Adding: "+ device_id + " Points: " + str(npoints) + " A("+str(naccelerations) +") "+ " B("+str(nbreaks) +") "+" city: " + city + "("+country+")")
	
	insert = Trips( username=username, device_id=device_id,
		firsttimestamp=firsttimestamp, lasttimestamp=lasttimestamp,
		firstpointlatitude=firstpointlatitude, firstpointlongitude=firstpointlongitude,
		lastpointlatitude=lastpointlatitude, lastpointlongitude=firstpointlongitude,
		geom=LineString(listpoints),
		city=city, country=country,citytype=citytype,
		duration=duration, distance=distance, velocity=velocity, npoints=npoints,
		naccelerations=naccelerations,nbreaks=nbreaks
	)

	insert.save()

	return 1





# Save the trips in the model
# Trips is a list of trips: [tripNumber][timestamp][device_id][latitude][longitude][speed]
# In the model insert:
# User ¿tripNumber? timestamp device_id latitude longitude
def insert_trips(request,trips):

	tripNumber = None
	device_id = None
	listpoints = []
	listcompletepoints = []
	firstpointlatitude = None
	firstpointlongitude = None
	lastpointlatitude = None
	lastpointlongitude = None
	firsttimestamp = None
	lasttimestamp = None
	point = None
	city = None
	country = None
	citytype = None

	for t in trips:

		# print t

		# If is the same tripNumber or
		# the list is empty add to the list (Is the first element) or
		if(tripNumber == t[0] or len(listpoints) == 0):
			# Add the point to the list
			completepoint = []
			completepoint.append(t[0]) #tripNumber
			completepoint.append(t[1]) #timestamp
			completepoint.append(t[2]) #device_id
			completepoint.append(t[3]) #latitude
			completepoint.append(t[4]) #longitude
			completepoint.append(t[5]) #speed
			listcompletepoints.append(completepoint)
			point = Point(float(t[4]),float(t[3]))
			listpoints.append(point)
			lasttimestamp = t[1]
			lastpointlatitude = t[3]
			lastpointlongitude = t[4]

			if(firstpointlatitude == None):
				firstpointlatitude = t[3]
				firstpointlongitude = t[4]
				device_id = t[2]
				firsttimestamp = t[1]
				#Calculated values
				# City and Country
				try:
					geolocator = Nominatim()
					location = geolocator.reverse(str(firstpointlatitude) + ", "+ str(firstpointlongitude))
					locjson = json.loads(json.dumps(location.raw))
					city = locjson['address']['city']
					citytype="city"
				except GeocoderTimedOut:
					print("Error: Geocode time out")
					continue
				except KeyError:
					try:
						city = locjson['address']['town']
						citytype="town"
					except KeyError:
						try:
							city = locjson['address']['village']
							citytype="village"
						except KeyError:
							try:
								city = locjson['address']['neighbourhood']
								citytype="neighbourhood"
							except KeyError:
								try:
									city = locjson['address']['hamlet']
									citytype="hamlet"
								except KeyError:
									#print(locjson)
									city = "Unknown"
									citytype="Unknown"
				except Exception as e:
					print("ERROR: " + str(e))
					continue

				try:
					country = locjson['address']['country']
				except KeyError:
					country = "Unknown"
		else:

			insert_ddbb(request,device_id,firsttimestamp,lasttimestamp,
				firstpointlatitude,firstpointlongitude,lastpointlatitude,lastpointlongitude,
				listpoints,listcompletepoints,city,country,citytype)
			# Clear the temporary list			
			listpoints = []
			listcompletepoints = []

			# Add the point to the list
			completepoint = []
			completepoint.append(t[0]) #tripNumber
			completepoint.append(t[1]) #timestamp
			completepoint.append(t[2]) #device_id
			completepoint.append(t[3]) #latitude
			completepoint.append(t[4]) #longitude
			completepoint.append(t[5]) #speed
			listcompletepoints.append(completepoint)
			point = Point(float(t[4]),float(t[3]))
			listpoints.append(point)
			lasttimestamp = t[1]
			lastpointlatitude = t[3]
			lastpointlongitude = t[4]
			firstpointlatitude = t[3]
			firstpointlongitude = t[4]
			device_id = t[2]
			firsttimestamp = t[1]
			#Calculated values
			# City and Country
			try:
				sleep(2) # after last line in if
				geolocator = Nominatim()
				location = geolocator.reverse(str(firstpointlatitude) + ", "+ str(firstpointlongitude))
				locjson = json.loads(json.dumps(location.raw))
				city = locjson['address']['city']
				citytype="city"
			except GeocoderTimedOut:
				print("Error: Geocode time out")
				continue
			except KeyError:
				try:
					city = locjson['address']['town']
					citytype="town"
				except KeyError:
					try:
						city = locjson['address']['village']
						citytype="village"
					except KeyError:
						try:
							city = locjson['address']['neighbourhood']
							citytype="neighbourhood"
						except KeyError:
							try:
								city = locjson['address']['hamlet']
								citytype="hamlet"
							except KeyError:
								#print(locjson)
								city = "Unknown"
								citytype="Unknown"
			except:
				print("ERROR")
				continue

			try:
				country = locjson['address']['country']
			except KeyError:
				country = "Unknown"


		tripNumber = t[0]

	# Finally insert the remaining list
	if(len(listpoints)>0):	
		insert_ddbb(request,device_id,firsttimestamp,lasttimestamp,
			firstpointlatitude,firstpointlongitude,lastpointlatitude,lastpointlongitude,
			listpoints,listcompletepoints,city,country,citytype)
		

def insert_ddbb(request,device_id,firsttimestamp,lasttimestamp,
	firstpointlatitude,firstpointlongitude,lastpointlatitude,lastpointlongitude,
	listpoints,listcompletepoints,city,country,citytype):

	duration = timedifference(datetime.strptime(firsttimestamp, '%Y-%m-%d %H:%M:%S'),datetime.strptime(lasttimestamp, '%Y-%m-%d %H:%M:%S')).total_seconds()
	distance = vincenty( (firstpointlatitude,firstpointlongitude), (lastpointlatitude,lastpointlongitude) ).meters
	npoints = len(listpoints)

	# no inserts
	if(npoints < 2):
		return
	if(distance == 0 or duration == 0):
		return

	try:
		velocity = (3.6)*(distance/duration)
	except ZeroDivisionError:
		velocity = 0
	

	#Determine accelerations
	gapac = 1.5
	gapbk = 0.5
	naccelerations = 0
	nbreaks = 0
	prevspeed=float(listcompletepoints[0][5])
	for completepoint in listcompletepoints:

		curspeed = float(completepoint[5])

		# Lecture error? or first/last point?
		if(curspeed !=0 and prevspeed !=0):
			if(prevspeed*gapac < curspeed):
				naccelerations+=1

			if(prevspeed*gapbk > curspeed):
				nbreaks+= 1

		prevspeed=curspeed


	print "Adding: "+ device_id + " Points: " + str(npoints) + " A("+str(naccelerations) +") "+ " B("+str(nbreaks) +") "+" city: " + city + "("+country+")"
	
	insert = Trips( username=request.user, device_id=device_id,
		firsttimestamp=firsttimestamp, lasttimestamp=lasttimestamp,
		firstpointlatitude=firstpointlatitude, firstpointlongitude=firstpointlongitude,
		lastpointlatitude=lastpointlatitude, lastpointlongitude=firstpointlongitude,
		geom=LineString(listpoints),
		city=city, country=country,citytype=citytype,
		duration=duration, distance=distance, velocity=velocity, npoints=npoints,
		naccelerations=naccelerations,nbreaks=nbreaks
	)

	insert.save()


	# Trips is a list of trips: [tripNumber][timestamp][device_id][latitude][longitude][speed]
	#for completepoint in listcompletepoints:
	#	Points(tripid=insert,timestamp=completepoint[1],device_id=completepoint[2],
	#		latitude=completepoint[3],longitude=completepoint[4],speed=completepoint[5]
	#		).save()


# Return all the points that have not been asociated to a trip
# Ordered by device_id and timestamp
def get_points():

	qs = Points.objects.filter(hasTrip=False).order_by('device_id','timestamp')

	print("Number of points to be analized: "+str(qs.count()))

	return qs


# Set true to the hasTrip atribute
def set_point_used(id):

	Points.objects.filter(id=id).update(hasTrip=True)

# Set all the points available for creating trips
def set_all_points_noused():
	Points.objects.all().update(hasTrip=False)