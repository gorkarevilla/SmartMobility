# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from django.contrib.gis import admin

from .models import Trips

# Register your models here.

admin.site.register(Trips, admin.GeoModelAdmin)