# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .forms import UploadFileForm

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
			# read_file(request.FILES['file'])
			messages.success(request,"File Uploaded Correctly")
			return HttpResponseRedirect('maposm.html')
		else:
			messages.error(request,"Error Uploading the File")
			return HttpResponseRedirect('upload.html')
	else:
		formupload = UploadFileForm()
	return render(request, 'behaviour/upload.html', {'formupload': formupload})


#Process the file
#def read_file(file):

