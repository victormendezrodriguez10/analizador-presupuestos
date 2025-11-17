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
import warnings
warnings.filterwarnings('ignore')

class ContratoAnalyzer:
    def __init__(self):
        self.connection = None

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

    def get_contratos_data(self, limit=5000):
        """Obtener datos de la tabla contratos"""
        query = f"SELECT * FROM contratos LIMIT {limit}"
        return pd.read_sql(query, self.connection)

    def get_contrato_structure(self):
        """Obtener estructura de la tabla contratos"""
        cursor = self.connection.cursor()
        cursor.execute("DESCRIBE contratos")
        columns = cursor.fetchall()
        cursor.close()
        return columns

    def extract_price_from_text(self, text):
        """Extraer precio de texto usando regex"""
        if pd.isna(text):
            return None

        text = str(text).replace('.', '').replace(',', '.')

        # Buscar patrones de precio
        patterns = [
            r'(\d+\.?\d*)\s*€',
            r'€\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*euros?',
            r'euros?\s*(\d+\.?\d*)',
            r'importe[:\s]*(\d+\.?\d*)',
            r'precio[:\s]*(\d+\.?\d*)',
            r'valor[:\s]*(\d+\.?\d*)',
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

    def clean_cpv_code(self, cpv_text):
        """Limpiar y extraer código CPV"""
        if pd.isna(cpv_text):
            return None

        cpv_pattern = r'(\d{8})'
        matches = re.findall(cpv_pattern, str(cpv_text))
        return matches[0] if matches else None

    def calculate_text_similarity(self, text1, text2):
        """Calcular similitud entre textos usando TF-IDF"""
        if pd.isna(text1) or pd.isna(text2):
            return 0

        vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
        try:
            tfidf_matrix = vectorizer.fit_transform([str(text1), str(text2)])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return similarity
        except:
            return 0

    def get_provincia_from_text(self, text):
        """Extraer provincia de texto"""
        if pd.isna(text):
            return None

        provincias_espana = [
            'Madrid', 'Barcelona', 'Valencia', 'Sevilla', 'Zaragoza', 'Málaga',
            'Murcia', 'Palma', 'Las Palmas', 'Bilbao', 'Alicante', 'Córdoba',
            'Valladolid', 'Vigo', 'Gijón', 'Hospitalet', 'Coruña', 'Granada',
            'Vitoria', 'Elche', 'Oviedo', 'Santa Cruz', 'Badalona', 'Cartagena',
            'Terrassa', 'Jerez', 'Sabadell', 'Móstoles', 'Alcalá', 'Pamplona',
            'Fuenlabrada', 'Almería', 'Leganés', 'Santander', 'Burgos',
            'Castellón', 'Alcorcón', 'Getafe', 'Salamanca', 'Huelva', 'Logroño',
            'Badajoz', 'San Sebastián', 'Albacete', 'Tarragona', 'León',
            'Cádiz', 'Jaén', 'Ourense', 'Reus', 'Torrelavega', 'Lugo'
        ]

        text_upper = str(text).upper()
        for provincia in provincias_espana:
            if provincia.upper() in text_upper:
                return provincia
        return None

    def find_similar_contratos(self, target_contrato, all_contratos):
        """Encontrar contratos similares basado en criterios específicos"""
        if target_contrato.empty:
            return pd.DataFrame()

        target_row = target_contrato.iloc[0]

        # Extraer información del contrato objetivo
        target_price = None
        target_provincia = None
        target_cpv = None
        target_objeto = ""

        # Buscar precio en diferentes columnas
        price_columns = ['precio', 'importe', 'valor', 'presupuesto', 'cantidad']
        for col in all_contratos.columns:
            col_lower = col.lower()
            if any(price_col in col_lower for price_col in price_columns):
                target_price = self.extract_price_from_text(target_row.get(col))
                if target_price:
                    break

        # Buscar provincia
        location_columns = ['provincia', 'ubicacion', 'lugar', 'localidad', 'direccion']
        for col in all_contratos.columns:
            col_lower = col.lower()
            if any(loc_col in col_lower for loc_col in location_columns):
                target_provincia = self.get_provincia_from_text(target_row.get(col))
                if target_provincia:
                    break

        # Buscar CPV
        cpv_columns = ['cpv', 'codigo']
        for col in all_contratos.columns:
            col_lower = col.lower()
            if any(cpv_col in col_lower for cpv_col in cpv_columns):
                target_cpv = self.clean_cpv_code(target_row.get(col))
                if target_cpv:
                    break

        # Buscar objeto
        objeto_columns = ['objeto', 'descripcion', 'servicio', 'titulo']
        for col in all_contratos.columns:
            col_lower = col.lower()
            if any(obj_col in col_lower for obj_col in objeto_columns):
                target_objeto = str(target_row.get(col, ""))
                break

        st.write("**Datos extraídos del contrato objetivo:**")
        st.write(f"- Precio objetivo: {target_price} €" if target_price else "- Precio: No encontrado")
        st.write(f"- Provincia objetivo: {target_provincia}" if target_provincia else "- Provincia: No encontrada")
        st.write(f"- CPV objetivo: {target_cpv}" if target_cpv else "- CPV: No encontrado")
        st.write(f"- Objeto: {target_objeto[:100]}..." if len(target_objeto) > 100 else f"- Objeto: {target_objeto}")

        # Filtrar contratos similares
        similar_contratos = []

        for idx, row in all_contratos.iterrows():
            if idx == target_contrato.index[0]:  # Saltar el contrato objetivo
                continue

            score = 0
            reasons = []

            # 1. Verificar provincia (criterio obligatorio)
            row_provincia = None
            for col in all_contratos.columns:
                col_lower = col.lower()
                if any(loc_col in col_lower for loc_col in location_columns):
                    row_provincia = self.get_provincia_from_text(row.get(col))
                    if row_provincia:
                        break

            if target_provincia and row_provincia:
                if target_provincia.upper() == row_provincia.upper():
                    score += 25
                    reasons.append(f"Misma provincia: {row_provincia}")

            # 2. Verificar precio (±30%)
            row_price = None
            for col in all_contratos.columns:
                col_lower = col.lower()
                if any(price_col in col_lower for price_col in price_columns):
                    row_price = self.extract_price_from_text(row.get(col))
                    if row_price:
                        break

            if target_price and row_price:
                price_diff = abs(row_price - target_price) / target_price
                if price_diff <= 0.30:  # ±30%
                    score += 25
                    reasons.append(f"Precio similar: {row_price} € (diff: {price_diff:.1%})")

            # 3. Verificar CPV similar
            row_cpv = None
            for col in all_contratos.columns:
                col_lower = col.lower()
                if any(cpv_col in col_lower for cpv_col in cpv_columns):
                    row_cpv = self.clean_cpv_code(row.get(col))
                    if row_cpv:
                        break

            if target_cpv and row_cpv:
                if target_cpv[:4] == row_cpv[:4]:  # Misma categoría principal
                    score += 20
                    reasons.append(f"CPV similar: {row_cpv}")

            # 4. Verificar similitud de objeto
            row_objeto = ""
            for col in all_contratos.columns:
                col_lower = col.lower()
                if any(obj_col in col_lower for obj_col in objeto_columns):
                    row_objeto = str(row.get(col, ""))
                    break

            if target_objeto and row_objeto:
                similarity = self.calculate_text_similarity(target_objeto, row_objeto)
                if similarity > 0.3:  # Similitud > 30%
                    score += similarity * 30
                    reasons.append(f"Objeto similar (sim: {similarity:.1%})")

            # 5. Bonus por fecha reciente
            fecha_columns = ['fecha', 'publicacion', 'adjudicacion']
            row_fecha = None
            for col in all_contratos.columns:
                col_lower = col.lower()
                if any(fecha_col in col_lower for fecha_col in fecha_columns):
                    try:
                        row_fecha = pd.to_datetime(row.get(col))
                        break
                    except:
                        continue

            if row_fecha:
                days_ago = (datetime.now() - row_fecha).days
                if days_ago < 365:  # Último año
                    recency_score = max(0, (365 - days_ago) / 365 * 10)
                    score += recency_score
                    reasons.append(f"Reciente: {days_ago} días")

            # Solo incluir si tiene score mínimo
            if score >= 25:  # Threshold mínimo
                similar_contratos.append({
                    'index': idx,
                    'score': score,
                    'reasons': reasons,
                    'precio': row_price,
                    'provincia': row_provincia,
                    'cpv': row_cpv,
                    'objeto': row_objeto[:100] + "..." if len(row_objeto) > 100 else row_objeto,
                    'row_data': row
                })

        # Ordenar por score descendente
        similar_contratos.sort(key=lambda x: x['score'], reverse=True)

        return similar_contratos[:20]  # Top 20

def main():
    st.title("📊 Analizador de Bajas Estadísticas - Contratos")
    st.sidebar.title("Configuración")

    # Inicializar analizador
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = ContratoAnalyzer()

    analyzer = st.session_state.analyzer

    # Conectar a la base de datos
    if not analyzer.connection:
        with st.spinner("Conectando a la base de datos..."):
            if analyzer.connect_to_database():
                st.success("✅ Conectado exitosamente a la base de datos")
            else:
                st.error("❌ No se pudo conectar a la base de datos")
                return

    # Mostrar estructura de la tabla
    with st.expander("📋 Estructura de la tabla contratos"):
        structure = analyzer.get_contrato_structure()
        structure_df = pd.DataFrame(structure, columns=['Campo', 'Tipo', 'Null', 'Key', 'Default', 'Extra'])
        st.dataframe(structure_df)

    # Cargar datos
    st.sidebar.subheader("Parámetros de carga")
    limit = st.sidebar.number_input("Límite de registros:", min_value=1000, max_value=10000, value=5000)

    if st.button("🔄 Cargar datos de contratos"):
        with st.spinner("Cargando datos..."):
            st.session_state.contratos_data = analyzer.get_contratos_data(limit)
            st.success(f"✅ Cargados {len(st.session_state.contratos_data)} contratos")

    # Análisis de bajas estadísticas
    if 'contratos_data' in st.session_state:
        data = st.session_state.contratos_data

        st.subheader("🎯 Búsqueda de Bajas Estadísticas")

        # Mostrar muestra de datos
        with st.expander("Ver muestra de datos"):
            st.dataframe(data.head(10))

        # Seleccionar contrato para analizar
        st.write("**Selecciona un contrato para buscar similares:**")

        # Crear selector basado en las primeras columnas disponibles
        display_columns = []
        for col in data.columns[:5]:  # Primeras 5 columnas para display
            display_columns.append(col)

        if len(data) > 0:
            # Crear texto descriptivo para cada contrato
            data['descripcion_contrato'] = data.apply(
                lambda row: f"ID: {row.name} | " + " | ".join([f"{col}: {str(row[col])[:50]}..." if len(str(row[col])) > 50 else f"{col}: {str(row[col])}" for col in display_columns]),
                axis=1
            )

            selected_index = st.selectbox(
                "Contrato objetivo:",
                options=data.index.tolist(),
                format_func=lambda x: data.loc[x, 'descripcion_contrato']
            )

            if st.button("🔍 Buscar Contratos Similares"):
                with st.spinner("Analizando con IA..."):
                    target_contrato = data.loc[[selected_index]]

                    similar_contratos = analyzer.find_similar_contratos(target_contrato, data)

                    if similar_contratos:
                        st.success(f"✅ Encontrados {len(similar_contratos)} contratos similares")

                        # Mostrar resultados
                        st.subheader("📈 Contratos Similares Encontrados")

                        for i, contrato in enumerate(similar_contratos[:10]):  # Top 10
                            with st.expander(f"🏆 #{i+1} - Score: {contrato['score']:.1f} puntos"):
                                col1, col2 = st.columns(2)

                                with col1:
                                    st.write("**Información extraída:**")
                                    st.write(f"- Precio: {contrato['precio']} €" if contrato['precio'] else "- Precio: No disponible")
                                    st.write(f"- Provincia: {contrato['provincia']}" if contrato['provincia'] else "- Provincia: No disponible")
                                    st.write(f"- CPV: {contrato['cpv']}" if contrato['cpv'] else "- CPV: No disponible")
                                    st.write(f"- Objeto: {contrato['objeto']}")

                                with col2:
                                    st.write("**Razones de similitud:**")
                                    for reason in contrato['reasons']:
                                        st.write(f"✓ {reason}")

                                # Datos completos del contrato
                                with st.expander("Ver datos completos"):
                                    st.write(contrato['row_data'].to_dict())

                        # Gráfico de scores
                        scores = [c['score'] for c in similar_contratos[:10]]
                        fig = px.bar(
                            x=[f"Contrato {i+1}" for i in range(len(scores))],
                            y=scores,
                            title="Puntuación de Similitud",
                            labels={'y': 'Score', 'x': 'Contratos'}
                        )
                        st.plotly_chart(fig)

                    else:
                        st.warning("⚠️ No se encontraron contratos similares con los criterios establecidos")

if __name__ == "__main__":
    main()