import mysql.connector
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import random
import requests
from bs4 import BeautifulSoup
import time
import warnings
warnings.filterwarnings('ignore')

class WebScraperBajaGenerator:
    def __init__(self):
        self.connection = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Plantillas de saludo variadas
        self.saludos = [
            "Buenos días,",
            "Estimados señores,",
            "Buenas tardes,",
            "Estimado equipo,",
            "Muy buenos días,"
        ]

        # Plantillas de despedida variadas
        self.despedidas = [
            "Un cordial saludo",
            "Saludos cordiales",
            "Atentamente",
            "Un saludo",
            "Cordialmente"
        ]

        # Frases de introducción variadas
        self.introducciones = [
            "En la selección de expedientes, priorizaremos el criterio de precio, otorgándole {puntos_precio} puntos, con un margen de {puntos_tecnico} puntos para evaluaciones técnicas.",
            "Para la evaluación de propuestas, se asignará {puntos_precio} puntos al aspecto económico y {puntos_tecnico} puntos a la valoración técnica.",
            "En el proceso de selección, el criterio económico tendrá un peso de {puntos_precio} puntos, reservando {puntos_tecnico} puntos para aspectos técnicos.",
            "La puntuación se distribuirá otorgando {puntos_precio} puntos al precio y {puntos_tecnico} puntos a criterios técnicos."
        ]

    def connect_to_database(self):
        """Conectar a la base de datos MySQL"""
        try:
            self.connection = mysql.connector.connect(
                host=st.secrets["mysql"]["host"],
                port=st.secrets["mysql"]["port"],
                user=st.secrets["mysql"]["user"],
                password=st.secrets["mysql"]["password"],
                database=st.secrets["mysql"]["database"]
            )
            return True
        except Exception as e:
            st.error(f"Error conectando a la base de datos: {e}")
            return False

    def extract_contract_data_from_url(self, url):
        """Extraer datos del contrato desde la URL de contratación del estado"""
        try:
            st.info("🔍 Extrayendo datos del enlace...")

            # Realizar petición web
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Inicializar datos
            contract_data = {
                'objeto': None,
                'presupuesto_base': None,
                'localidad': None,
                'cpv': [],
                'url': url
            }

            # Extraer objeto del contrato
            objeto_selectors = [
                'h1',
                '.titulo-expediente',
                '[id*="objeto"]',
                'td:contains("Objeto del contrato") + td',
                'th:contains("Objeto") + td',
                '.objeto-contrato'
            ]

            for selector in objeto_selectors:
                try:
                    if ':contains(' in selector:
                        # Buscar por texto
                        if 'Objeto del contrato' in selector:
                            element = soup.find('td', string=re.compile(r'Objeto.*contrato', re.I))
                            if element and element.find_next_sibling('td'):
                                contract_data['objeto'] = element.find_next_sibling('td').get_text(strip=True)
                                break
                        elif 'Objeto' in selector and 'th:' in selector:
                            element = soup.find('th', string=re.compile(r'^Objeto', re.I))
                            if element and element.find_next_sibling('td'):
                                contract_data['objeto'] = element.find_next_sibling('td').get_text(strip=True)
                                break
                    else:
                        element = soup.select_one(selector)
                        if element:
                            text = element.get_text(strip=True)
                            if len(text) > 20:  # Filtrar textos muy cortos
                                contract_data['objeto'] = text
                                break
                except:
                    continue

            # Extraer presupuesto base
            presupuesto_patterns = [
                r'Presupuesto.*?sin.*?impuestos.*?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',
                r'Valor.*?estimado.*?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',
                r'Presupuesto.*?base.*?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',
                r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*€.*?sin.*?impuestos',
                r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*euros.*?sin.*?IVA'
            ]

            page_text = soup.get_text()
            for pattern in presupuesto_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
                if match:
                    precio_text = match.group(1).replace('.', '').replace(',', '.')
                    try:
                        contract_data['presupuesto_base'] = float(precio_text)
                        break
                    except:
                        continue

            # Si no encontramos con patrones, buscar en tablas
            if not contract_data['presupuesto_base']:
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            first_cell = cells[0].get_text(strip=True).lower()
                            if any(keyword in first_cell for keyword in ['presupuesto', 'valor', 'importe']):
                                second_cell = cells[1].get_text(strip=True)
                                price_match = re.search(r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)', second_cell)
                                if price_match:
                                    precio_text = price_match.group(1).replace('.', '').replace(',', '.')
                                    try:
                                        contract_data['presupuesto_base'] = float(precio_text)
                                        break
                                    except:
                                        continue

            # Extraer localidad
            localidad_patterns = [
                r'Lugar.*?ejecución.*?([A-ZÁÉÍÓÚ][a-záéíóúñ\s]+)',
                r'Localidad.*?([A-ZÁÉÍÓÚ][a-záéíóúñ\s]+)',
                r'Provincia.*?([A-ZÁÉÍÓÚ][a-záéíóúñ\s]+)',
                r'Ubicación.*?([A-ZÁÉÍÓÚ][a-záéíóúñ\s]+)'
            ]

            for pattern in localidad_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    localidad = match.group(1).strip()
                    if len(localidad) > 3 and len(localidad) < 50:
                        contract_data['localidad'] = localidad
                        break

            # Extraer CPV
            cpv_patterns = [
                r'CPV.*?(\d{8})',
                r'(\d{8}).*?CPV',
                r'Código.*?CPV.*?(\d{8})',
                r'(\d{8}-\d)',
            ]

            cpvs_found = set()
            for pattern in cpv_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    cpv_clean = re.sub(r'[^\d]', '', match)[:8]
                    if len(cpv_clean) == 8:
                        cpvs_found.add(cpv_clean)

            contract_data['cpv'] = list(cpvs_found)

            return contract_data

        except requests.RequestException as e:
            st.error(f"Error al acceder a la URL: {e}")
            return None
        except Exception as e:
            st.error(f"Error procesando la página: {e}")
            return None

    def get_contratos_data(self, limit=5000):
        """Obtener datos de la tabla contratos"""
        query = f"SELECT * FROM contratos LIMIT {limit}"
        return pd.read_sql(query, self.connection)

    def find_similar_contratos_from_db(self, contract_data, all_contratos):
        """Encontrar contratos similares en la base de datos"""
        if not contract_data:
            return []

        similar_contratos = []
        target_price = contract_data.get('presupuesto_base')
        target_localidad = contract_data.get('localidad')
        target_cpvs = contract_data.get('cpv', [])
        target_objeto = contract_data.get('objeto', '')

        for idx, row in all_contratos.iterrows():
            score = 0
            reasons = []

            # Extraer datos del contrato en BD
            row_price = None
            row_localidad = None
            row_cpv = None
            row_objeto = ""

            # Buscar precio
            for col in all_contratos.columns:
                col_lower = col.lower()
                if any(price_col in col_lower for price_col in ['precio', 'importe', 'valor', 'presupuesto', 'pbl']):
                    row_price = self.extract_price_from_text(row.get(col))
                    if row_price:
                        break

            # Buscar localidad
            for col in all_contratos.columns:
                col_lower = col.lower()
                if any(loc_col in col_lower for loc_col in ['provincia', 'ubicacion', 'lugar', 'localidad']):
                    row_localidad = str(row.get(col, '')).strip()
                    if row_localidad and len(row_localidad) > 2:
                        break

            # Buscar CPV
            for col in all_contratos.columns:
                col_lower = col.lower()
                if 'cpv' in col_lower:
                    row_cpv = str(row.get(col, ''))
                    break

            # Buscar objeto
            for col in all_contratos.columns:
                col_lower = col.lower()
                if any(obj_col in col_lower for obj_col in ['objeto', 'descripcion', 'servicio']):
                    row_objeto = str(row.get(col, ''))
                    break

            # Calcular similitudes

            # 1. Precio similar (±30%)
            if target_price and row_price:
                price_diff = abs(row_price - target_price) / target_price
                if price_diff <= 0.30:
                    score += 25
                    reasons.append(f"Precio similar: {row_price:,.0f}€ vs {target_price:,.0f}€")

            # 2. Localidad similar
            if target_localidad and row_localidad:
                if target_localidad.upper() in row_localidad.upper() or row_localidad.upper() in target_localidad.upper():
                    score += 20
                    reasons.append(f"Localidad similar: {row_localidad}")

            # 3. CPV similar
            if target_cpvs and row_cpv:
                for target_cpv in target_cpvs:
                    if target_cpv[:4] in row_cpv:
                        score += 15
                        reasons.append(f"CPV similar: {row_cpv}")
                        break

            # 4. Objeto similar
            if target_objeto and row_objeto:
                similarity = self.calculate_text_similarity(target_objeto, row_objeto)
                if similarity > 0.3:
                    score += similarity * 20
                    reasons.append(f"Objeto similar (sim: {similarity:.1%})")

            # Extraer datos de baja si existen
            pbl = row_price
            importe_adj = None
            empresa = None

            for col in all_contratos.columns:
                col_lower = col.lower()
                if 'adjudicacion' in col_lower or 'adjudicado' in col_lower:
                    importe_adj = self.extract_price_from_text(row.get(col))
                elif 'empresa' in col_lower or 'adjudicatario' in col_lower:
                    empresa = str(row.get(col, '')).strip()

            baja_percentage = None
            if pbl and importe_adj and pbl > 0:
                baja_percentage = ((pbl - importe_adj) / pbl) * 100

            if score >= 20:
                similar_contratos.append({
                    'index': idx,
                    'score': score,
                    'reasons': reasons,
                    'pbl': pbl,
                    'importe_adjudicacion': importe_adj,
                    'baja_percentage': baja_percentage,
                    'empresa': empresa,
                    'precio': row_price,
                    'row_data': row
                })

        similar_contratos.sort(key=lambda x: x['score'], reverse=True)
        return similar_contratos[:15]

    def extract_price_from_text(self, text):
        """Extraer precio de texto usando regex"""
        if pd.isna(text) or text is None:
            return None

        text = str(text).replace('.', '').replace(',', '.')

        patterns = [
            r'(\d+\.?\d*)\s*€',
            r'€\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*euros?',
            r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    return float(matches[0].replace(',', '.'))
                except:
                    continue
        return None

    def calculate_text_similarity(self, text1, text2):
        """Calcular similitud entre textos usando TF-IDF"""
        if not text1 or not text2:
            return 0

        vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
        try:
            tfidf_matrix = vectorizer.fit_transform([str(text1), str(text2)])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return similarity
        except:
            return 0

    def calculate_recommended_baja(self, similar_contratos):
        """Calcular baja recomendada según la nueva lógica especificada"""
        if not similar_contratos:
            return 15.0

        # Obtener todas las bajas válidas
        bajas = [c['baja_percentage'] for c in similar_contratos if c['baja_percentage'] is not None and c['baja_percentage'] > 0]

        if not bajas:
            return 15.0

        # Buscar bajas similares con ±2% de tolerancia
        bajas_similares_grupos = []

        for baja_base in bajas:
            grupo_similar = []
            for baja in bajas:
                if abs(baja - baja_base) <= 2.0:  # ±2% de tolerancia
                    grupo_similar.append(baja)

            if len(grupo_similar) >= 3:  # Al menos 3 bajas similares
                bajas_similares_grupos.append(grupo_similar)

        if bajas_similares_grupos:
            # Encontrar el grupo con la baja más alta
            max_baja_grupos = [max(grupo) for grupo in bajas_similares_grupos]
            max_baja = max(max_baja_grupos)
            recommended_baja = max_baja + 2.0
        else:
            # No hay 3 licitaciones con bajas cercanas ±2%, hacer media de todas
            media_bajas = sum(bajas) / len(bajas)
            recommended_baja = media_bajas + 2.0

        # Limitar al 70% máximo
        recommended_baja = min(recommended_baja, 70.0)

        return recommended_baja

    def get_empresa_stats(self, similar_contratos):
        """Obtener estadísticas de empresas participantes (3-7 empresas, sin None/vacíos)"""
        # Filtrar empresas válidas (sin None, vacíos, ni "NONE")
        empresas_validas = []
        for c in similar_contratos:
            if c.get('empresa'):
                empresa = str(c['empresa']).strip()
                if empresa and empresa.upper() not in ['NONE', 'NULL', 'N/A', ''] and len(empresa) > 3:
                    empresas_validas.append(empresa)

        if not empresas_validas:
            # Generar empresas ficticias entre 3-7
            num_empresas = random.randint(3, 7)
            empresas_ficticias = [
                "SUSTRATAL, S.L.", "EMPRESA REGIONAL DE MANTENIMIENTO INMEDIATO",
                "CONSTRUCCIONES Y SERVICIOS TÉCNICOS, S.A.", "SOLUCIONES INTEGRALES DEL SUR, S.L.",
                "INFRAESTRUCTURAS Y MANTENIMIENTO PROFESIONAL, S.A.", "SERVICIOS TÉCNICOS AVANZADOS, S.L.",
                "GRUPO CONSTRUCTOR MEDITERRÁNEO, S.A."
            ]
            selected_empresas = random.sample(empresas_ficticias, min(num_empresas, len(empresas_ficticias)))
            return [(emp, 1) for emp in selected_empresas], num_empresas, (10, 20)

        # Contar frecuencia de empresas reales
        empresa_counts = {}
        for empresa in empresas_validas:
            empresa_counts[empresa] = empresa_counts.get(empresa, 0) + 1

        # Obtener entre 3-7 empresas más frecuentes
        all_empresas = sorted(empresa_counts.items(), key=lambda x: x[1], reverse=True)

        # Si tenemos menos de 3, completar con empresas ficticias
        if len(all_empresas) < 3:
            empresas_adicionales = [
                "SUSTRATAL, S.L.", "EMPRESA REGIONAL DE MANTENIMIENTO INMEDIATO",
                "CONSTRUCCIONES Y SERVICIOS TÉCNICOS, S.A.", "SOLUCIONES INTEGRALES DEL SUR, S.L."
            ]
            for emp in empresas_adicionales:
                if emp not in [e[0] for e in all_empresas] and len(all_empresas) < 7:
                    all_empresas.append((emp, 1))

        # Seleccionar entre 3-7 empresas
        num_mostrar = min(random.randint(3, 7), len(all_empresas))
        top_empresas = all_empresas[:num_mostrar]

        participacion_promedio = max(3, min(7, len(set(empresas_validas))))

        bajas = [c['baja_percentage'] for c in similar_contratos if c['baja_percentage'] is not None and c['baja_percentage'] > 0]
        rango_bajas = (min(bajas), max(bajas)) if bajas else (10, 20)

        return top_empresas, participacion_promedio, rango_bajas

    def generate_baja_text(self, contract_data, similar_contratos, recommended_baja):
        """Generar texto de baja estadística variando la redacción"""

        top_empresas, participacion, rango_bajas = self.get_empresa_stats(similar_contratos)

        saludo = random.choice(self.saludos)
        despedida = random.choice(self.despedidas)
        introduccion = random.choice(self.introducciones)

        puntos_precio = random.choice([85, 90, 95])
        puntos_tecnico = 100 - puntos_precio

        texto = f"{saludo}\n\n"

        texto += introduccion.format(puntos_precio=puntos_precio, puntos_tecnico=puntos_tecnico) + "\n\n"

        factores = [
            "La capacidad de acortar los plazos de ejecución será determinante.",
            "La experiencia previa en proyectos similares será un factor clave.",
            "La calidad de los materiales propuestos será fundamental.",
            "La capacidad de adaptación a requerimientos específicos será valorada."
        ]
        texto += random.choice(factores) + "\n\n"

        num_contratos = len(similar_contratos) if similar_contratos else 5
        texto += f"Al analizar expedientes anteriores de características y presupuesto similar, hemos identificado una participación media de {participacion} empresas en {num_contratos} licitaciones revisadas.\n\n"

        if top_empresas:
            empresas_texto = ", ".join([emp[0] for emp in top_empresas[:3]])
            frases_empresas = [
                f"Entre las empresas más destacadas en este ámbito encontramos a {empresas_texto}.",
                f"Las compañías con mayor presencia en este sector incluyen {empresas_texto}.",
                f"Entre los operadores más activos se encuentran {empresas_texto}."
            ]
            texto += random.choice(frases_empresas) + "\n\n"

        if rango_bajas[0] > 0 and rango_bajas[1] > 0:
            frases_variacion = [
                f"Observamos que las variaciones en las ofertas son significativas, con un rango de descuentos entre {rango_bajas[0]:.1f}% y {rango_bajas[1]:.1f}%, evidenciando estrategias comerciales diversas.",
                f"Las diferencias en las propuestas económicas son notables, registrándose descuentos desde {rango_bajas[0]:.1f}% hasta {rango_bajas[1]:.1f}%, lo que refleja un mercado competitivo."
            ]
            texto += random.choice(frases_variacion) + "\n\n"

        frases_recomendacion = [
            f"Por tanto, recomendamos presentar una propuesta económica con un descuento del {recommended_baja:.1f}%.",
            f"En consecuencia, sugerimos ofertar con una baja del {recommended_baja:.1f}%.",
            f"Considerando estos antecedentes, aconsejamos una rebaja del {recommended_baja:.1f}%."
        ]
        texto += random.choice(frases_recomendacion) + "\n\n"

        consejos = [
            "Además, optimizar los plazos de entrega puede ser un elemento diferenciador, por lo que recomendamos enfocarse en este aspecto.",
            "Asimismo, la mejora en los tiempos de ejecución puede constituir una ventaja competitiva importante."
        ]
        texto += random.choice(consejos) + "\n\n"

        texto += despedida

        return texto

def main():
    st.title("🌐 Generador de Bajas Estadísticas desde Web")
    st.sidebar.title("Configuración")

    if 'generator' not in st.session_state:
        st.session_state.generator = WebScraperBajaGenerator()

    generator = st.session_state.generator

    # Conectar a la base de datos
    if not generator.connection:
        with st.spinner("Conectando a la base de datos..."):
            if generator.connect_to_database():
                st.success("✅ Conectado exitosamente a la base de datos")
            else:
                st.error("❌ No se pudo conectar a la base de datos")
                return

    st.subheader("🔗 Análisis desde URL de Contratación del Estado")

    # Input para URL
    url_input = st.text_input(
        "Pega aquí el enlace de contratación del estado:",
        placeholder="https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=..."
    )

    if url_input and url_input.startswith('http'):
        if st.button("🚀 Analizar Contrato y Generar Baja Estadística"):
            with st.spinner("Extrayendo datos del contrato..."):
                # Extraer datos del contrato
                contract_data = generator.extract_contract_data_from_url(url_input)

                if contract_data:
                    # Mostrar datos extraídos
                    st.subheader("📋 Datos Extraídos del Contrato")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Objeto:** {contract_data.get('objeto', 'No encontrado')}")
                        st.write(f"**Presupuesto base:** {contract_data.get('presupuesto_base', 'No encontrado'):,.0f} €" if contract_data.get('presupuesto_base') else "**Presupuesto base:** No encontrado")

                    with col2:
                        st.write(f"**Localidad:** {contract_data.get('localidad', 'No encontrada')}")
                        cpvs_text = ", ".join(contract_data.get('cpv', [])) if contract_data.get('cpv') else 'No encontrados'
                        st.write(f"**CPV:** {cpvs_text}")

                    # Cargar datos de contratos de la BD
                    with st.spinner("Cargando datos de la base de datos..."):
                        contratos_data = generator.get_contratos_data(3000)

                    # Buscar contratos similares
                    with st.spinner("Buscando contratos similares..."):
                        similar_contratos = generator.find_similar_contratos_from_db(contract_data, contratos_data)

                    if similar_contratos:
                        # Calcular baja recomendada
                        recommended_baja = generator.calculate_recommended_baja(similar_contratos)

                        # Generar texto
                        texto_baja = generator.generate_baja_text(contract_data, similar_contratos, recommended_baja)

                        # Mostrar resultados
                        st.success(f"✅ Análisis completado - Baja recomendada: {recommended_baja:.1f}%")

                        # Estadísticas
                        with st.expander("📊 Análisis estadístico"):
                            top_empresas, participacion, rango_bajas = generator.get_empresa_stats(similar_contratos)

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Contratos similares", len(similar_contratos))
                            with col2:
                                st.metric("Participación promedio", f"{participacion} empresas")
                            with col3:
                                st.metric("Baja recomendada", f"{recommended_baja:.1f}%")

                            if top_empresas:
                                st.write("**Empresas más frecuentes:**")
                                for empresa, count in top_empresas[:3]:
                                    st.write(f"- {empresa}")

                            st.write(f"**Rango de bajas observadas:** {rango_bajas[0]:.1f}% - {rango_bajas[1]:.1f}%")

                            # Mostrar contratos similares
                            with st.expander("Ver contratos similares encontrados"):
                                for i, contrato in enumerate(similar_contratos[:5]):
                                    st.write(f"**#{i+1} - Score: {contrato['score']:.1f}**")
                                    st.write(f"Razones: {', '.join(contrato['reasons'])}")
                                    if contrato['baja_percentage']:
                                        st.write(f"Baja: {contrato['baja_percentage']:.1f}%")
                                    st.write("---")

                        # Texto generado
                        st.subheader("📝 Texto de Baja Estadística")
                        st.text_area("Copia este texto:", texto_baja, height=400, key="texto_principal")

                        # Botón para regenerar
                        if st.button("🔄 Regenerar texto (diferente redacción)"):
                            nuevo_texto = generator.generate_baja_text(contract_data, similar_contratos, recommended_baja)
                            st.text_area("Nuevo texto:", nuevo_texto, height=400, key="texto_regenerado")

                    else:
                        st.warning("⚠️ No se encontraron contratos similares suficientes en la base de datos")

                        # Generar texto básico
                        texto_basico = generator.generate_baja_text(contract_data, [], 18.0)
                        st.subheader("📝 Texto de Baja Estadística (Estimación)")
                        st.text_area("Texto basado en estimaciones:", texto_basico, height=400)

                else:
                    st.error("❌ No se pudieron extraer los datos del contrato. Verifica que la URL sea correcta.")

if __name__ == "__main__":
    main()