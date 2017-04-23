from django.conf.urls import url

from . import views

from djgeojson.views import GeoJSONLayerView
from .models import Trips

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^maposm', views.maposm, name='maposm'),
    url(r'^upload', views.upload, name='upload'),
    url(r'^display', views.display, name='display'),
    url(r'^logout', views.user_logout, name='logout'),
    url(r'^data.geojson$', GeoJSONLayerView.as_view(model=Trips), name='data'),
]