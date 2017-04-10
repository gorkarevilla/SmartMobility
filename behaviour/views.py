# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .forms import UploadFileForm

import csv
from datetime import datetime
from io import BytesIO

# Create your views here.
@require_http_methods(["GET"])
def index(request):
	return render (request, 'behaviour/index.html')

@require_http_methods(["GET"])
def maposm(request):
	return render (request, 'behaviour/maposm.html')

def upload(request):
	if request.method == 'POST':
		formupload = UploadFileForm(request.POST, request.FILES)
		if formupload.is_valid():
			spacer = " "
			gaptime = 60
			positions = clean_file(request.FILES['file'],spacer)
			determine_trips(positions,gaptime)
			messages.success(request,"File Uploaded Correctly")
			return HttpResponseRedirect('maposm.html')
		else:
			messages.error(request,"Error Uploading the File")
			return HttpResponseRedirect('upload.html')
	else:
		formupload = UploadFileForm()
	return render(request, 'behaviour/upload.html', {'formupload': formupload})


#Process the file
#Format: 
# dateTime device_id id latitude longitude speed
# 2017-01-24T09:49:24.063Z za0 c3e0b6fcd96d0a329903887ec39cb5835780db17 40.42951587 -3.64513278 0
# 
def clean_file(file,spacer):

	positions = []

	reader = csv.reader(file, delimiter=str(spacer))

	cleanfile = BytesIO()
	writter = csv.writer(cleanfile, delimiter=str(spacer))
	counter = 0
	#for line in file:
	for line in reader:
		#Check the line
		try:
			point = []
			# 2017-02-02T19:18:36.063Z
			timestamp = datetime.strptime(line[0], '%Y-%m-%dT%H:%M:%S.%fZ')
			point.append(timestamp.strftime("%Y-%m-%d %H:%M:%S"))
			point.append(line[1])
			point.append(line[3])
			point.append(line[4])

			positions.append(point)

			#writter.writerow([strtimestamp, device_id, latitude, longitude])
			
		except ValueError:
			# 2017-01-24
			#datetime1 = datetime.strptime(line[0], '%Y-%m-%d')
			continue

		counter+=1
	print counter

	return positions

# Determine Trips
def determine_trips(positions,gaptime):
	
	for pos in positions:
		print pos