# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-04-28 12:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('behaviour', '0011_auto_20170428_1151'),
    ]

    operations = [
        migrations.AddField(
            model_name='trips',
            name='naccelerations',
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='trips',
            name='nbreaks',
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
    ]
