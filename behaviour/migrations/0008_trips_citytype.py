# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-04-27 14:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('behaviour', '0007_auto_20170427_0944'),
    ]

    operations = [
        migrations.AddField(
            model_name='trips',
            name='citytype',
            field=models.CharField(blank=True, default=None, max_length=20, null=True),
        ),
    ]
