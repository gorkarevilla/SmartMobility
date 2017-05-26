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
from datetime import time

from .models import Trips, Points, PointsAttribs
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
	
	return render (request, 'behaviour/display.html', {'userform': userform})


@require_http_methods(["GET"])
def user_logout(request): 
	logout(request)
	messages.add_message(request, messages.SUCCESS, 'You have successfully loged out!')
	return HttpResponseRedirect('/')







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
	gapdistance = 5000 # in meters

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
						procpoints = save_trip(request,trip)
						# Save or print an error
						if(procpoints == 0):
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


# Populate the table PointsAttribs with all the calculations based on the points directly 
def load_points(request):

	# Get all the points with no PointsAttribs asocciated
	qs = Points.objects.filter(pointsattribs = None)
	
	# IF is not empty
	if(qs.exists()):

		with transaction.atomic(): # Everything in the same transaction (faster but more memory)

			npoints = 0
			for point in qs:
		
				#pointid = point.id
				timestamp = point.timestamp
				#device_id = point.device_id
				#latitude = point.latitude
				#longitude = point.longitude
				#speed = point.speed

				numberdayofweek = timestamp.weekday() #0 to monday, 6 to sunday

				dayofweek = None
				isweekend = False
				if (numberdayofweek == 0): dayofweek = "Monday"  
				if (numberdayofweek == 1): dayofweek = "Tuesday"  
				if (numberdayofweek == 2): dayofweek = "Wednesday"  
				if (numberdayofweek == 3): dayofweek = "Thursday"  
				if (numberdayofweek == 4): dayofweek = "Friday"  
				if (numberdayofweek == 5): dayofweek = "Saturday" ; isweekend = True  
				if (numberdayofweek == 6): dayofweek = "Sunday" ; isweekend = True

				print("Adding Point: "+str(point)+" on: "+dayofweek+ "("+str(isweekend)+")")

				insert = PointsAttribs(point=point,dayofweek=dayofweek,isweekend=isweekend)
				insert.save()
				npoints+=1

			print("Number of points loaded: "+str(npoints))
			messages.success(request,"Points loaded Correctly")
			return HttpResponseRedirect('maposm.html')

	else:
		messages.error(request, 'No points to be processed!')
		return HttpResponseRedirect('maposm.html')

# Download a CSV file with all the trips
def download_trips(request):
	# Create the HttpResponse object with the appropriate CSV header.
	response = HttpResponse(content_type='text/csv')
	response['Content-Disposition'] = 'attachment; filename="trips.csv"'

	writer = csv.writer(response)

	tripslist = Trips.objects.exclude(city="Unknown").exclude(state="Unknown").exclude(country="Unknown").filter(firsttimerange="latenight",isweekend="False").values_list('id', 'firsttimestamp', 'city', 'state', 'country', 'citytype', 'duration', 'distance', 'velocity', 'npoints', 'naccelerations', 'nbreaks','pnaccelerations', 'pnbreaks', 'dayofweek', 'isweekend')

	writer.writerow(["tripid", "firsttimestamp", "city", "state", "country", "citytype", "duration", "distance", "velocity", "npoints", "naccelerations", "nbreaks", "pnaccelerations", "pnbreaks", "dayofweek", "isweekend"])	
	for tripid, firsttimestamp, city, state, country, citytype, duration, distance, velocity, npoints, naccelerations, nbreaks, pnaccelerations, pnbreaks, dayofweek, isweekend in tripslist:

		writer.writerow([tripid, firsttimestamp, city.encode('utf-8').strip(), state.encode('utf-8').strip(), country.encode('utf-8').strip(), citytype, duration, distance, velocity, npoints, naccelerations, nbreaks, pnaccelerations, pnbreaks, dayofweek, isweekend])
		


	return response

# Download a CSV file with all the points
def download_points(request):
	# Create the HttpResponse object with the appropriate CSV header.
	response = HttpResponse(content_type='text/csv')
	response['Content-Disposition'] = 'attachment; filename="points.csv"'

	writer = csv.writer(response)

	pointslist = Points.objects.values_list('timestamp', 'device_id', 'latitude', 'longitude', 'speed', 'pointsattribs')

	writer.writerow(["timestamp", "device_id", "latitude", "longitude", "speed", "dayofweek", "isweekend"])	
	for timestamp, device_id, latitude, longitude, speed, pointsattribs in pointslist:
		attribs = PointsAttribs.objects.get(pk=pointsattribs)
		writer.writerow([timestamp, device_id, latitude, longitude, speed, attribs.dayofweek, attribs.isweekend])
		


	return response

# Update stress of all the trips
def update_stress(request):
	print("Updating Stress...")
	with transaction.atomic():
		for tid,firsttimerange,lasttimerange,isweekend,city,country,state,pnaccelerations,pnbreaks in Trips.objects.values_list('id','firsttimerange','lasttimerange','isweekend','city','country','state','pnaccelerations','pnbreaks'):
			stresslevel = calculate_stress(firsttimerange,lasttimerange,isweekend,city,country,state,pnaccelerations,pnbreaks)
			Trips.objects.filter(id=tid).update(stresslevel=stresslevel)

	messages.success(request, 'Trips Stresslevel updated!')
	return HttpResponseRedirect('maposm.html')




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
			print("ERROR: Geocode time out")
			raise GeocoderTimedOut
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
			raise Exception
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

def gettimerange(thedatestamp):
	#print("Getting timerange...")

	timestamp = thedatestamp.time()

	timerange = None
	if (timestamp >= time(7,0,0) and timestamp < time(9,0,0)): timerange = "earlymorning" #7-9  
	if (timestamp >= time(9,0,0) and timestamp < time(12,0,0)): timestamp = "morning" #9-12   
	if (timestamp >= time(12,0,0) and timestamp < time(15,0,0)): timerange = "earlyafternoon" #12-15  
	if (timestamp >= time(15,0,0) and timestamp < time(20,0,0)): timerange = "afternoon" #15-20  
	if (timestamp >= time(20,0,0) and timestamp < time(23,0,0)): timerange = "night" #20-23  
	if (timestamp >= time(23,0,0) or timestamp < time(7,0,0)): timerange = "latenight" #23-7  


	if(timerange == None):
		return "Unknown"

	return timerange

# Determine the stress level of a trip
# Return a integer as:
# 	-1: Error
#	0: Low
#	50: Normal
#	100: High
def calculate_stress(firsttimerange,lasttimerange,isweekend,city,country,state,pnaccelerations,pnbreaks):
	# [max][min]
	# pa -> percentage accelerations
	# pb -> percentage breaks

	### Default values for a empty ddbb, this has been calculated with the training dataset (1week)

	## Laboral
	# EarlyMorning
	palem= [0.29 , 0.15]
	pblem= [0.16 , 0.07]
	# Morning
	palm=  [0.29 , 0.15]
	pblm=  [0.16 , 0.07]
	# EarlyAfternoon
	palea= [0.22 , 0.10]
	pblea= [0.12 , 0.03]
	# Afternoon
	pala=  [0.27 , 0.13]
	pbla=  [0.13 , 0.03]
	# Night
	paln=  [0.26 , 0.12]
	pbln=  [0.12 , 0.02]
	# LateNight
	palln= [0.27 , 0.14]
	pblln= [0.13 , 0.03]

	## Weekend
	paw=   [0.27 , 0.13]
	pbw=   [0.13 , 0.02]


	# points for stress level
	level = 50

	learn = False
	if(learn):
		#check the values on the DDBB
		print("Calculating max and min values...")



	if(isweekend):
		level-=10 #Bonus for weekend
		if(pnaccelerations>paw[0]): level+=25
		if(pnaccelerations<paw[1]): level-=25 
		if(pnbreaks>pbw[0]): level+=25
		if(pnbreaks<pbw[1]): level-=25
	else:
		if(firsttimerange=="earlymorning"):
			if(pnaccelerations>palem[0]): level+=25
			if(pnaccelerations<palem[1]): level-=25 
			if(pnbreaks>pblem[0]): level+=25
			if(pnbreaks<pblem[1]): level-=25
		elif(firsttimerange=="morning"):
			if(pnaccelerations>palm[0]): level+=25
			if(pnaccelerations<palm[1]): level-=25 
			if(pnbreaks>pblm[0]): level+=25
			if(pnbreaks<pblm[1]): level-=25
		elif(firsttimerange=="earlyafternoon"):
			if(pnaccelerations>palea[0]): level+=25
			if(pnaccelerations<palea[1]): level-=25 
			if(pnbreaks>pblea[0]): level+=25
			if(pnbreaks<pblea[1]): level-=25
		elif(firsttimerange=="afternoon"):
			if(pnaccelerations>pala[0]): level+=25
			if(pnaccelerations<pala[1]): level-=25 
			if(pnbreaks>pbla[0]): level+=25
			if(pnbreaks<pbla[1]): level-=25
		elif(firsttimerange=="night"):
			if(pnaccelerations>paln[0]): level+=25
			if(pnaccelerations<paln[1]): level-=25 
			if(pnbreaks>pbln[0]): level+=25
			if(pnbreaks<pbln[1]): level-=25
		elif(firsttimerange=="latenight"):
			if(pnaccelerations>palln[0]): level+=25
			if(pnaccelerations<palln[1]): level-=25 
			if(pnbreaks>pblln[0]): level+=25
			if(pnaccelerations<pblln[1]): level-=25


	if(level<=25):
		print("Level: Low") 
		return 0
	elif(level>25 and level<=75): 
		print("Level: Medium") 
		return 50
	elif(level>75): 
		print("Level: High") 
		return 100
	else: 
		return -1

#####
#####  DDBB FUNCTIONS
#####

# [timestamp, device_id, latitude, longitude, speed]
def insert_points(positions):
	with transaction.atomic():
		for pos in positions:
			insert = Points(timestamp=pos[0],device_id=pos[1],latitude=pos[2],longitude=pos[3],speed=pos[4])
			insert.save()





# Save the trip in the model
# Trip is a list of points: [id][timestamp][device_id][latitude][longitude][speed]
def save_trip(request,trip):
	#print("Saving trip...")

	#Set minimuns, 
	minpoints = 10 # greater than 2
	mindistance = 100 # greater than 0, meters (tries to avoid circular trips)
	minduration = 30 # greater than 0, seconds
	
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

	duration = timedifference(firsttimestamp,lasttimestamp).total_seconds()
	distance = vincenty( (firstpointlatitude,firstpointlongitude), (lastpointlatitude,lastpointlongitude) ).meters
	npoints = len(trip)



	# Empty List
	if(npoints == 0):
		print("ERROR: List Empty!")
		return 0
	# no inserts
	if(npoints < minpoints):
		print("ERROR: Points less than "+minpoints)
		return 0
	if(distance < mindistance):
		print("ERROR: Distance is less than "+mindistance)
		return 0
	if(duration < minduration):
		print("ERROR: Duration is less than "+minduration)
		return 0

	try:
		velocity = (3.6)*(distance/duration)
	except ZeroDivisionError:
		print("ERROR: Zero Division, duration is zero")
		velocity = 0

	# Calculate the timerange string
	firsttimerange = gettimerange(firsttimestamp)
	lasttimerange = gettimerange(lasttimestamp)


	#Create the Geom (list of points)
	listpoints = []
	for p in trip:
		point = Point(float(p[4]),float(p[3])) # (longitude,latitude)
		listpoints.append(point)

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

	pnaccelerations = float(float(naccelerations)/float(npoints))
	pnbreaks = float(float(nbreaks)/float(npoints))

	try:
		# Get the data of the position, it would take 1 sec to be done
		firstposition = geoposition(firstpoint[3],firstpoint[4])
	except Exception as e:
		return 0
	
	city = firstposition.city
	country = firstposition.country
	citytype = firstposition.citytype
	state = firstposition.state


	numberdayofweek = firsttimestamp.weekday() #0 to monday, 6 to sunday

	dayofweek = None
	isweekend = False
	if (numberdayofweek == 0): dayofweek = "Monday"  
	if (numberdayofweek == 1): dayofweek = "Tuesday"  
	if (numberdayofweek == 2): dayofweek = "Wednesday"  
	if (numberdayofweek == 3): dayofweek = "Thursday"  
	if (numberdayofweek == 4): dayofweek = "Friday"  
	if (numberdayofweek == 5): dayofweek = "Saturday" ; isweekend = True  
	if (numberdayofweek == 6): dayofweek = "Sunday" ; isweekend = True

	stresslevel = calculate_stress(firsttimerange,lasttimerange,isweekend,city,country,state,pnaccelerations,pnbreaks)

	print("Adding: "+ device_id + " Points: ""A("+str(pnaccelerations) +") "+ "B("+str(pnbreaks) +") "+" city: " + city + "("+state+")"+"["+country+"]")
	
	insert = Trips( username=username, device_id=device_id,
		firsttimestamp=firsttimestamp, lasttimestamp=lasttimestamp, 
		firsttimerange=firsttimerange, lasttimerange=lasttimerange,
		firstpointlatitude=firstpointlatitude, firstpointlongitude=firstpointlongitude,
		lastpointlatitude=lastpointlatitude, lastpointlongitude=firstpointlongitude,
		geom=LineString(listpoints),
		city=city, country=country,citytype=citytype,state=state,
		duration=duration, distance=distance, velocity=velocity, npoints=npoints,
		naccelerations=naccelerations,nbreaks=nbreaks,
		pnaccelerations=pnaccelerations,pnbreaks=pnbreaks,
		dayofweek=dayofweek,isweekend=isweekend,
		stresslevel=stresslevel
	)

	insert.save()

	set_points_used(trip)

	return npoints



# Return all the points that have not been asociated to a trip
# Ordered by device_id and timestamp
def get_points():
	#ALL
	qs = Points.objects.filter(hasTrip=False).order_by('device_id','timestamp')

	#By Device_id
	#qs = Points.objects.filter(hasTrip=False,device_id="b10").order_by('device_id','timestamp')

	#By Date
	#datefilter = datetime(2017,1,3) 
	#qs =Points.objects.filter(hasTrip=False,timestamp__date=datefilter).order_by('device_id','timestamp')


	print("Number of points to be analized: "+str(qs.count()))

	return qs


# Delete all the trips and set all the points availables to calculate trips
def delete_trips(request):
	Trips.objects.all().delete()
	set_all_points_noused()
	print("All Data Deleted!")
	return HttpResponseRedirect('maposm.html')

# Detele all the points in the DDBB
def delete_points(request):
	Points.objects.all().delete()
	print("All Points Deleted!")
	return HttpResponseRedirect('maposm.html')

# Set true to the hasTrip atribute all the points in the list trips
# id is value 0
def set_points_used(trips):

	for p in trips:
		Points.objects.filter(id=p[0]).update(hasTrip=True)

# Set all the points available for creating trips
def set_all_points_noused():
	Points.objects.all().update(hasTrip=False)