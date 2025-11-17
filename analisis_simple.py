import streamlit as st
import psycopg2
import pandas as pd
import json
import requests
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Análisis de Bajas Estadísticas", page_icon="📊", layout="wide")

st.title("📊 Análisis de Bajas Estadísticas")
st.markdown("---")

# Conexión a base de datos
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        database=st.secrets["postgres"]["database"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        port=st.secrets["postgres"]["port"]
    )

def extraer_datos_xml(url):
    """Extraer datos básicos del XML"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        # Extraer datos básicos
        datos = {
            'titulo': '',
            'organismo': '',
            'presupuesto': 0,
            'cpv': '',
            'ubicacion': '',
            'criterios': []
        }

        # Buscar título
        for elem in root.iter():
            tag_lower = elem.tag.lower()
            if 'title' in tag_lower or 'titulo' in tag_lower:
                if elem.text and len(elem.text.strip()) > 10:
                    datos['titulo'] = elem.text.strip()
                    break

        # Buscar organismo
        for elem in root.iter():
            tag_lower = elem.tag.lower()
            if 'buyername' in tag_lower or 'organizacion' in tag_lower or 'contracting' in tag_lower:
                if elem.text and len(elem.text.strip()) > 5:
                    datos['organismo'] = elem.text.strip()
                    break

        # Buscar presupuesto
        for elem in root.iter():
            tag_lower = elem.tag.lower()
            if 'estimatedoverallcontractamount' in tag_lower or 'budgetamount' in tag_lower or 'totalamount' in tag_lower:
                if elem.text:
                    try:
                        datos['presupuesto'] = float(elem.text.strip().replace(',', '.'))
                        break
                    except:
                        pass

        # Buscar CPV
        for elem in root.iter():
            tag_lower = elem.tag.lower()
            if 'cpv' in tag_lower:
                cpv_value = elem.get('CODE') or elem.text
                if cpv_value and len(cpv_value) >= 4:
                    datos['cpv'] = ''.join(filter(str.isdigit, cpv_value))
                    break

        # Buscar ubicación
        for elem in root.iter():
            tag_lower = elem.tag.lower()
            if 'cityname' in tag_lower or 'city' in tag_lower or 'town' in tag_lower:
                if elem.text and len(elem.text.strip()) > 2:
                    datos['ubicacion'] = elem.text.strip()
                    break

        # Buscar criterios
        for elem in root.iter():
            tag_lower = elem.tag.lower()
            if 'awardingcrit' in tag_lower or 'criterion' in tag_lower:
                criterio = {}
                for child in elem:
                    child_tag = child.tag.lower()
                    if 'description' in child_tag or 'name' in child_tag:
                        criterio['descripcion'] = child.text
                    elif 'weight' in child_tag or 'punto' in child_tag:
                        criterio['peso'] = child.text

                if criterio:
                    datos['criterios'].append(criterio)

        return datos
    except Exception as e:
        st.error(f"Error al procesar XML: {e}")
        return None

def buscar_contratos(conn, cpv, presupuesto_min, presupuesto_max, limit=10):
    """Buscar contratos similares por CPV"""
    cpv_digits = ''.join(filter(str.isdigit, str(cpv)))[:4]

    if not cpv_digits or len(cpv_digits) < 4:
        return []

    query = f"""
    SELECT
        titulo,
        entidad_compradora as organismo,
        importe_total,
        importe_adjudicacion,
        adjudicatario,
        numero_licitadores,
        fecha_publicacion,
        ROUND(((importe_total - importe_adjudicacion) / NULLIF(importe_total, 0) * 100)::numeric, 2) as baja,
        cpv,
        provincia
    FROM adjudicaciones_metabase
    WHERE importe_total IS NOT NULL
    AND importe_adjudicacion IS NOT NULL
    AND importe_total > 0
    AND importe_adjudicacion > 0
    AND importe_total != importe_adjudicacion
    AND cpv::text ~ '{cpv_digits}'
    AND importe_total BETWEEN {presupuesto_min} AND {presupuesto_max}
    ORDER BY fecha_publicacion DESC
    LIMIT {limit}
    """

    try:
        cur = conn.cursor()
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        results = []

        for row in cur.fetchall():
            contrato = dict(zip(columns, row))

            # Extraer nombre de empresa
            adj_raw = contrato['adjudicatario']
            empresa = 'N/A'
            if adj_raw:
                try:
                    adj_str = str(adj_raw)
                    if adj_str.startswith('['):
                        adj_array = json.loads(adj_str)
                        if adj_array and 'adjudicatario' in adj_array[0]:
                            empresa = adj_array[0]['adjudicatario'].get('name', 'N/A')
                    elif adj_str.startswith('{'):
                        adj_dict = json.loads(adj_str)
                        if 'adjudicatario' in adj_dict:
                            empresa = adj_dict['adjudicatario'].get('name', 'N/A')
                    else:
                        empresa = adj_str[:60]
                except:
                    empresa = str(adj_raw)[:60] if adj_raw else 'N/A'

            contrato['empresa'] = empresa
            results.append(contrato)

        cur.close()
        return results
    except Exception as e:
        st.error(f"Error en búsqueda: {e}")
        return []

# Interfaz principal
st.markdown("### 🔗 Análisis desde URL XML")

xml_url = st.text_input(
    "Introduce la URL del XML del contrato:",
    placeholder="https://contrataciondelestado.es/FileSystem/servlet/...",
    help="Pega la URL completa del XML"
)

col1, col2 = st.columns(2)
with col1:
    cpv_manual = st.text_input(
        "CPV (opcional - si no se encuentra en el XML):",
        placeholder="72413000",
        help="Introduce el código CPV si el XML no lo contiene"
    )
with col2:
    presupuesto_manual = st.number_input(
        "Presupuesto (opcional - si no se encuentra en el XML):",
        min_value=0.0,
        value=0.0,
        step=1000.0,
        help="Introduce el presupuesto si el XML no lo contiene"
    )

if st.button("🚀 Analizar", type="primary"):
    if not xml_url:
        st.warning("Por favor, introduce una URL")
    else:
        with st.spinner("Descargando y analizando XML..."):
            datos = extraer_datos_xml(xml_url)

        if not datos:
            st.error("No se pudo procesar el XML")
        else:
            # Usar valores manuales si están disponibles
            if cpv_manual:
                datos['cpv'] = cpv_manual
                st.info(f"✏️ Usando CPV manual: {cpv_manual}")
            if presupuesto_manual > 0:
                datos['presupuesto'] = presupuesto_manual
                st.info(f"✏️ Usando presupuesto manual: €{presupuesto_manual:,.2f}")

            st.success("✅ XML procesado correctamente")

            # Mostrar datos del contrato
            st.markdown("---")
            st.markdown("### 📋 Datos del Contrato")

            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Organismo:** {datos['organismo']}")
                st.write(f"**Ubicación:** {datos['ubicacion']}")
            with col2:
                st.write(f"**Presupuesto:** €{datos['presupuesto']:,.2f}")
                st.write(f"**CPV:** {datos['cpv']}")

            st.write(f"**Título:** {datos['titulo']}")

            st.markdown("---")
            st.markdown("### ⚖️ Criterios de Adjudicación")

            if datos['criterios']:
                for i, crit in enumerate(datos['criterios'], 1):
                    desc = crit.get('descripcion', f'Criterio {i}')
                    peso = crit.get('peso', '')
                    st.write(f"**{i}.** {desc.upper()}: **{peso}**" if peso else f"**{i}.** {desc.upper()}")
            else:
                st.info("No se encontraron criterios en el XML")

            # Buscar contratos similares
            st.markdown("---")
            st.markdown("### 🔍 Búsqueda de Contratos Similares")

            presupuesto = datos['presupuesto']
            if presupuesto > 0:
                pres_min = presupuesto * 0.5
                pres_max = presupuesto * 1.5

                with st.spinner(f"Buscando contratos con CPV {datos['cpv'][:4]}..."):
                    conn = get_connection()
                    contratos = buscar_contratos(conn, datos['cpv'], pres_min, pres_max, limit=10)

                if not contratos:
                    st.warning(f"⚠️ No se encontraron contratos similares para CPV {datos['cpv']}")
                else:
                    st.success(f"✅ Encontrados {len(contratos)} contratos similares")

                    # Calcular estadísticas
                    bajas = [c['baja'] for c in contratos if c['baja']]
                    empresas = {}
                    for c in contratos:
                        emp = c['empresa']
                        if emp and emp != 'N/A' and len(emp) > 3:
                            empresas[emp] = empresas.get(emp, 0) + 1

                    if bajas:
                        baja_min = min(bajas)
                        baja_max = max(bajas)
                        baja_prom = sum(bajas) / len(bajas)

                        st.markdown("---")
                        st.markdown("### 📊 Resultados del Análisis")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("🎯 Baja Recomendada", f"{baja_prom:.2f}%")
                        with col2:
                            st.metric("📈 Contratos Analizados", len(contratos))
                        with col3:
                            num_lic_prom = sum([c['numero_licitadores'] or 0 for c in contratos]) / len(contratos)
                            st.metric("👥 Licitadores Promedio", f"{num_lic_prom:.0f}")

                        st.markdown("---")
                        st.markdown("### 🏆 Análisis de Mercado")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**📈 Estadísticas:**")
                            st.write(f"• Rango de bajas: **{baja_min:.1f}% - {baja_max:.1f}%**")
                            st.write(f"• Baja media: **{baja_prom:.1f}%**")
                            st.write(f"• Participación promedio: **{int(num_lic_prom)} empresas**")

                        with col2:
                            if empresas:
                                st.markdown("**🏢 Empresas Más Activas:**")
                                sorted_emp = sorted(empresas.items(), key=lambda x: x[1], reverse=True)
                                for emp, count in sorted_emp[:5]:
                                    st.write(f"• {emp} ({count})")

                        st.markdown("---")
                        st.markdown(f"### 📋 Contratos Similares ({len(contratos)})")

                        for i, c in enumerate(contratos, 1):
                            with st.container():
                                col1, col2 = st.columns([3, 1])

                                with col1:
                                    titulo = c['titulo']
                                    st.markdown(f"**{i}. {titulo[:80]}{'...' if len(titulo) > 80 else ''}**")
                                    st.write(f"📍 **Organismo:** {c['organismo']}")
                                    if c['empresa'] != 'N/A':
                                        st.write(f"🏢 **Adjudicatario:** {c['empresa']}")

                                with col2:
                                    st.write(f"💰 **Presupuesto:** €{c['importe_total']:,.2f}")
                                    st.write(f"💵 **Adjudicación:** €{c['importe_adjudicacion']:,.2f}")
                                    st.write(f"📉 **Baja:** {c['baja']:.2f}%")
                                    st.write(f"👥 **Licitadores:** {c['numero_licitadores'] or 0}")
                                    fecha = str(c['fecha_publicacion'])[:10]
                                    st.write(f"📅 {fecha}")

                                st.divider()
            else:
                st.warning("No se pudo extraer el presupuesto del XML")

st.markdown("---")
st.caption("Análisis basado en datos históricos del Portal de Contratación del Estado")
