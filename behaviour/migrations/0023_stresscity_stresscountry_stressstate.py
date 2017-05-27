# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-27 10:34
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('behaviour', '0022_auto_20170527_1033'),
    ]

    operations = [
        migrations.CreateModel(
            name='StressCity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('city', models.IntegerField(unique=True)),
                ('high', models.IntegerField(default=0)),
                ('mid', models.IntegerField(default=0)),
                ('low', models.IntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='StressCountry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('country', models.IntegerField(unique=True)),
                ('high', models.IntegerField(default=0)),
                ('mid', models.IntegerField(default=0)),
                ('low', models.IntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='StressState',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.IntegerField(unique=True)),
                ('high', models.IntegerField(default=0)),
                ('mid', models.IntegerField(default=0)),
                ('low', models.IntegerField(default=0)),
            ],
        ),
    ]