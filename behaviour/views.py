# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.http import HttpResponse

from django.views.decorators.http import require_http_methods

# Create your views here.
@require_http_methods(["GET"])
def index(request):
    return render (request, 'behaviour/index.html')

@require_http_methods(["GET"])
def maposm(request):
	return render (request, 'behaviour/maposm.html')
