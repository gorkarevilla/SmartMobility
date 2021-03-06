# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-27 10:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('behaviour', '0024_auto_20170527_1036'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stresscity',
            name='id',
        ),
        migrations.RemoveField(
            model_name='stresscountry',
            name='id',
        ),
        migrations.RemoveField(
            model_name='stressstate',
            name='id',
        ),
        migrations.AlterField(
            model_name='stresscity',
            name='city',
            field=models.CharField(max_length=30, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='stresscountry',
            name='country',
            field=models.CharField(max_length=30, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='stressstate',
            name='state',
            field=models.CharField(max_length=30, primary_key=True, serialize=False),
        ),
    ]
