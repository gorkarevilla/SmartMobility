# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from django.contrib.gis import admin

from .models import Trips, Points,PointsAttribs

# Register your models here.

admin.site.register(Trips, admin.GeoModelAdmin)
admin.site.register(Points, admin.GeoModelAdmin)
admin.site.register(PointsAttribs, admin.GeoModelAdmin)