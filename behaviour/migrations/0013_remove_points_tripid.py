# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-12 08:37
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('behaviour', '0012_auto_20170428_1237'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='points',
            name='tripid',
        ),
    ]