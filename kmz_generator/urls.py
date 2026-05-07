
from django.contrib import admin
from django.urls import path
from exportador import views  # ← Importar desde la app correcta



urlpatterns = [
    path('', views.formulario_kmz, name='formulario_kmz'),
    path('generar_kmz/', views.generar_kmz_por_trafo, name='generar_kmz_por_trafo'),
    path('generar_kmz_total/', views.generar_kmz_total, name='generar_kmz_total'),  # ← si implementas esta vista
    path('api/circuitos/', views.api_circuitos, name='api_circuitos'),
    path('api/trafos/', views.api_trafos, name='api_trafos'),
    path("generar_pdf_trafo/", views.generar_pdf_trafo_view, name="generar_pdf_trafo"),
]
