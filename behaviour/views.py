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

from .models import Trips
from django.contrib.gis.geos import LineString, Point

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from geopy.distance import vincenty

# Create your views here.


@require_http_methods(["GET"])
def index(request):
	userform = LoginForm()
	return render (request, 'behaviour/index.html', {'userform': userform})

@require_http_methods(["GET"])
def maposm(request):
	userform = LoginForm()
	return render (request, 'behaviour/maposm.html', {'userform': userform})

def upload(request):
	if request.method == 'POST':
		formupload = UploadFileForm(request.POST, request.FILES)
		if formupload.is_valid():
			spacer = " "
			gaptime = 120
			positions = clean_file(request.FILES['file'],spacer)
			trips = determine_trips(positions,gaptime)
			if (request.user.is_authenticated):
				insert_trips(request,trips)
				messages.success(request,"File Saved Correctly")
				return HttpResponseRedirect('maposm.html')
			else :
				messages.success(request,"File Processed Correctly")
				return HttpResponseRedirect('maposm.html')
		else:
			messages.error(request,"Error Uploading the File")
			return HttpResponseRedirect('upload.html')
	else:
		userform = LoginForm()
		formupload = UploadFileForm()
		return render(request, 'behaviour/upload.html', {'formupload': formupload, 'userform': userform})

@require_http_methods(["GET"])
def display(request):
	userform = LoginForm()
	return render (request, 'behaviour/display.html', {'userform': userform})


@require_http_methods(["GET"])
def user_logout(request): 
	logout(request)
	messages.add_message(request, messages.SUCCESS, 'You have successfully loged out!')
	return HttpResponseRedirect('/')

#Process the file
#Format input: 
# dateTime device_id id latitude longitude speed
# 2017-01-24T09:49:24.063Z za0 c3e0b6fcd96d0a329903887ec39cb5835780db17 40.42951587 -3.64513278 0
#
#Format output:
# positions = 	[
#				[timestamp] [device_id] [latitude] [longitude]
# 				]
# 
def clean_file(file,spacer):

	positions = []

	reader = csv.reader(file, delimiter=str(spacer))

	counter = 0
	#for line in file:
	for line in reader:
		#Check the line
		try:
			point = []
			# 2017-02-02T19:18:36.063Z
			timestamp = datetime.strptime(line[0], '%Y-%m-%dT%H:%M:%S.%fZ')
			point.append(timestamp.strftime("%Y-%m-%d %H:%M:%S"))
			point.append(line[1]) # device_id
			point.append(line[3]) # latitude
			point.append(line[4]) # longitude

			positions.append(point)

			#writter.writerow([strtimestamp, device_id, latitude, longitude])
			
		except ValueError:
			# 2017-01-24
			#datetime1 = datetime.strptime(line[0], '%Y-%m-%d')
			print "ValueError: " + str(line)
			continue

		counter+=1
	# print counter

	return positions

# Determine Trips
# Delete the points and determine the trips by timestamp and device_id
def determine_trips(positions,gaptime):

	#List of trips
	trips = []

	#Number of trips
	tripNumber = 0

	#Control if the point is the last point of a list of linked points
	isLastPoint = 0
	#NOTE: N^2! can be done with better performace
	for pos in positions:
		try:
			thispos = pos
			nextpos = positions[positions.index(pos)+1] 
			# print "Pos: "+thispos[0] + " Next: " + nextpos[0]
			

			thisdate = datetime.strptime(thispos[0], '%Y-%m-%d %H:%M:%S')
			nextdate = datetime.strptime(nextpos[0], '%Y-%m-%d %H:%M:%S')

			# If the time is close, is part of a trip
			if (timedifference(nextdate,thisdate)<timedelta(seconds=gaptime) ):

				#List of points for trip [tripNumber][timestamp][device_id][latitud][longitude]
				point = []
				point.append(tripNumber) # tripNumber
				point.append(thispos[0]) # timestamp
				point.append(thispos[1]) # device_id
				point.append(thispos[2]) # latitude
				point.append(thispos[3]) # longitude

				trips.append(point)

				isLastPoint=1

				#print point

			else:


				# Include the last point to the trip
				if(isLastPoint):
					#List of points for trip [tripNumber][timestamp][device_id][latitude][longitude]
					point = []
					point.append(tripNumber) # tripNumber
					point.append(thispos[0]) # timestamp
					point.append(thispos[1]) # device_id
					point.append(thispos[2]) # latitude
					point.append(thispos[3]) # longitude

					trips.append(point)					

				tripNumber+=1
				isLastPoint=0

		except IndexError:
			print "IndexError: " + str(pos)
			continue

	return trips

# Returns the deltatime between two datatimes
def timedifference(t1,t2):
	if(t1<t2):
		return t2-t1
	else:
		return t1-t2




# Save the trips in the model
# Trips is a list of trips: [tripNumber][timestamp][device_id][latitud][longitude]
# In the model insert:
# User ¿tripNumber? timestamp device_id latitude longitude
def insert_trips(request,trips):

	tripNumber = None
	listpoints = []
	firstpointlatitude = None
	firstpointlongitude = None
	lastpointlatitude = None
	lastpointlongitude = None
	firsttimestamp = None
	lasttimestamp = None
	point = None
	city = None
	country = None

	for t in trips:

		# print t

		# If is the same tripNumber or
		# the list is empty add to the list (Is the first element) or
		if(tripNumber == t[0] or len(listpoints) == 0):
			# Add the point to the list
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
				except GeocoderTimedOut:
					print("Error: Geocode time out")
				except KeyError:
					city = "Unknown"
				try:
					country = locjson['address']['country']
				except KeyError:
					country = "Unknown"			
		else:

			insert_ddbb(request,device_id,firsttimestamp,lasttimestamp,
				firstpointlatitude,firstpointlongitude,lastpointlatitude,lastpointlongitude,
				listpoints,city,country)
			# Clear the temporary list			
			listpoints = []


			# Add the point to the list
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
				geolocator = Nominatim()
				location = geolocator.reverse(str(firstpointlatitude) + ", "+ str(firstpointlongitude))
				locjson = json.loads(json.dumps(location.raw))
				city = locjson['address']['city']
			except GeocoderTimedOut:
				print("Error: Geocode time out")
			except KeyError:
				city = "Unknown"
			try:
				country = locjson['address']['country']
			except KeyError:
				country = "Unknown"


		tripNumber = t[0]

	# Finally insert the remaining list
	insert_ddbb(request,device_id,firsttimestamp,lasttimestamp,
		firstpointlatitude,firstpointlongitude,lastpointlatitude,lastpointlongitude,
		listpoints,city,country)
		

def insert_ddbb(request,device_id,firsttimestamp,lasttimestamp,
	firstpointlatitude,firstpointlongitude,lastpointlatitude,lastpointlongitude,
	listpoints,city,country):

	duration = timedifference(datetime.strptime(firsttimestamp, '%Y-%m-%d %H:%M:%S'),datetime.strptime(lasttimestamp, '%Y-%m-%d %H:%M:%S')).total_seconds()
	distance = vincenty( (firstpointlatitude,firstpointlongitude), (lastpointlatitude,lastpointlongitude) ).meters
	try:
		velocity = (3.6)*(distance/duration)
	except ZeroDivisionError:
		velocity = 0
		

	print "Adding: "+ device_id + " FT: " + str(firsttimestamp) + " FP: " + str(firstpointlatitude)
	
	Trips( username=request.user, device_id=device_id,
		firsttimestamp=firsttimestamp, lasttimestamp=lasttimestamp,
		firstpointlatitude=firstpointlatitude, firstpointlongitude=firstpointlongitude,
		lastpointlatitude=lastpointlatitude, lastpointlongitude=firstpointlongitude,
		geom=LineString(listpoints),
		city=city, country=country,
		duration=duration, distance=distance, velocity=velocity
	).save()






