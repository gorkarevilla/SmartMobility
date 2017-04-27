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

	firsttimestamp = models.DateTimeField()
	lasttimestamp = models.DateTimeField()

	firstpointlatitude = models.FloatField()
	firstpointlongitude = models.FloatField()

	lastpointlatitude = models.FloatField()
	lastpointlongitude = models.FloatField()

	

	#GeoDjango-specific fields
	geom = gismodels.LineStringField() # geom is the Field to be drawn (all the points)

	#Calculated fields
	city = models.CharField(max_length=20)
	country = models.CharField(max_length=20)

	duration = models.FloatField(default=None, blank=True, null=True)
	distance = models.FloatField(default=None, blank=True, null=True)
	velocity = models.FloatField(default=None, blank=True, null=True)
	npoints = models.IntegerField(default=None, blank=True, null=True)

	naccelerations = models.IntegerField(default=None, blank=True, null=True)
	nbreaks = models.IntegerField(default=None, blank=True, null=True)


	# Returns the string representation of the model.
	def __unicode__(self):              # __str__ on Python !=2
		return self.city + " : " + str(self.device_id) + " @ "+ str(self.firsttimestamp) + " - " + str(self.lasttimestamp) + " - " + str(self.distance)