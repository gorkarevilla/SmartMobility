# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.db import models
from django.contrib.gis.db import models as gismodels

# Create your models here.

# Model with all the points
class Trips(models.Model):
	# Regular Fields
	username = models.ForeignKey(
		User,on_delete=models.CASCADE)
	device_id = models.CharField(max_length=4)

	#GeoDjango-specific fields
	points = gismodels.LineStringField()

	# Returns the string representation of the model.
	def __str__(self):              # __unicode__ on Python 2
		return self.name