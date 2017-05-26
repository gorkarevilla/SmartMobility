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
    url(r'^loadtrips', views.load_trips, name='loadtrips'),
    url(r'^loadpoints', views.load_points, name='loadpoints'),
    url(r'^updatestress', views.update_stress, name='updatestress'),
    url(r'^downloadtrips', views.download_trips, name='downloadtrips'),
    url(r'^downloadpoints', views.download_points, name='downloadpoints'),
    url(r'^deletetrips', views.delete_trips, name='deletetrips'),
    url(r'^deletepoints', views.delete_points, name='deletepoints'),
    url(r'^data.geojson$', GeoJSONLayerView.as_view(model=Trips), name='data'),
]