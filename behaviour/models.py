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
	
	firsttimerange = models.CharField(max_length=20, default=None, blank=True, null=True)
	lasttimerange = models.CharField(max_length=20, default=None, blank=True, null=True)

	firstpointlatitude = models.FloatField()
	firstpointlongitude = models.FloatField()

	lastpointlatitude = models.FloatField()
	lastpointlongitude = models.FloatField()

	

	#GeoDjango-specific fields
	geom = gismodels.LineStringField() # geom is the Field to be drawn (all the points)

	#Calculated fields
	city = models.CharField(max_length=20, default=None, blank=True, null=True)
	country = models.CharField(max_length=20, default=None, blank=True, null=True)
	state = models.CharField(max_length=20,default=None, blank=True, null=True)
	citytype = models.CharField(max_length=20, default=None, blank=True, null=True)

	duration = models.FloatField(default=None, blank=True, null=True)
	distance = models.FloatField(default=None, blank=True, null=True)
	velocity = models.FloatField(default=None, blank=True, null=True)
	npoints = models.IntegerField(default=None, blank=True, null=True)

	naccelerations = models.IntegerField(default=None, blank=True, null=True)
	nbreaks = models.IntegerField(default=None, blank=True, null=True)
	pnaccelerations = models.FloatField(default=None, blank=True, null=True) #percentage of points
	pnbreaks = models.FloatField(default=None, blank=True, null=True) #percentage of points

	dayofweek = models.CharField(max_length=10,default=None, blank=True, null=True)
	isweekend = models.BooleanField(default=False, blank=True) 

	# Returns the string representation of the model.
	def __unicode__(self):              # __str__ on Python !=2
		return self.city + " : " + str(self.device_id) + " @ "+ str(self.firsttimestamp) + " - " + str(self.lasttimestamp) + " - " + str(self.distance)



class Points(models.Model):
	# Regular Fields
	timestamp = models.DateTimeField()
	device_id = models.CharField(max_length=4) 
	latitude = models.FloatField()
	longitude = models.FloatField()
	speed = models.FloatField()
	hasTrip = models.BooleanField(default=False,db_index=True)

	def __unicode__(self):              # __str__ on Python !=2
		return str(self.device_id) + " - "+ str(self.timestamp) + " @ " + str(self.latitude) + " : " + str(self.latitude) + " (" +str(self.speed)+")" + " ["+str(self.hasTrip)+"]"



class PointsAttribs(models.Model):
	# Relation Field
	point = models.OneToOneField(
		Points,
		on_delete=models.CASCADE,
		primary_key=True,
    )

	# Regular Fields
	dayofweek = models.CharField(max_length=10,default=None, blank=True, null=True)
	isweekend = models.BooleanField(default=False, blank=True) 
	

	def __unicode__(self):              # __str__ on Python !=2
		return str(self.point) + " @ " + str(self.dayofweek) + " (" +str(self.isweekend)+")"
