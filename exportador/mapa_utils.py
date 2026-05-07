import folium

def generar_mapa_html(lat, lon, path="mapa.html"):
    m = folium.Map(location=[lat, lon], zoom_start=17)
    folium.Marker([lat, lon], popup="TRAFO").add_to(m)
    m.save(path)
    return path
