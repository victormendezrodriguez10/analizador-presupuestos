# 📊 Análisis de Bajas Estadísticas - App Privada

Esta guía te llevará paso a paso para tener tu aplicación **accesible desde tu iPad desde cualquier lugar**, de forma **100% privada**.

## 🎯 Lo que vas a conseguir

- ✅ Tu app funcionando en la nube (sin necesidad de tener tu Mac encendido)
- ✅ Acceso desde tu iPad desde cualquier lugar con internet
- ✅ **100% privada** - solo tú podrás acceder
- ✅ Gratis (usando Streamlit Cloud)

---

## 📋 Requisitos previos

Solo necesitas crear 2 cuentas gratuitas:

1. **GitHub** - para guardar tu código de forma segura
2. **Streamlit Cloud** - para ejecutar tu aplicación

---

## 🚀 Paso 1: Crear cuenta en GitHub (5 minutos)

1. Ve a [https://github.com/signup](https://github.com/signup)
2. Introduce tu email y crea una contraseña
3. Elige un nombre de usuario
4. Verifica tu email (revisa tu bandeja de entrada)
5. **¡Listo!** Ya tienes cuenta de GitHub

---

## 📤 Paso 2: Subir tu código a GitHub (10 minutos)

### Opción A: Usando GitHub Desktop (MÁS FÁCIL) ⭐

1. **Descarga GitHub Desktop:**
   - Ve a [https://desktop.github.com](https://desktop.github.com)
   - Descarga e instala la aplicación
   - Ábrela e inicia sesión con tu cuenta de GitHub

2. **Crea un repositorio:**
   - En GitHub Desktop, haz clic en: **File → New Repository**
   - Nombre: `presupuestos-app`
   - Descripción: "App de análisis de bajas estadísticas"
   - Local Path: Elige tu escritorio (Desktop)
   - ✅ Marca "Initialize this repository with a README"
   - Haz clic en **Create Repository**

3. **Copia tus archivos:**
   - Abre Finder y ve a Desktop → `presupuestos-app`
   - Copia **TODOS los archivos** de tu carpeta `presupuestos` EXCEPTO:
     - NO copies la carpeta `__pycache__`
     - NO copies el archivo `.DS_Store`
   - Pega los archivos en la carpeta `presupuestos-app`

4. **Sube los archivos a GitHub:**
   - Vuelve a GitHub Desktop
   - Verás una lista de archivos cambiados
   - En la esquina inferior izquierda:
     - Summary: "Primera versión de la app"
     - Description: (déjalo en blanco)
   - Haz clic en **Commit to main**
   - Haz clic en **Publish repository**
   - ⚠️ **MUY IMPORTANTE:** Desmarca "Keep this code private" (queremos que sea público para usar Streamlit Cloud gratis)
   - Haz clic en **Publish Repository**

### Opción B: Subiendo archivos directamente en GitHub.com (ALTERNATIVA)

1. Ve a [https://github.com](https://github.com)
2. Inicia sesión
3. Haz clic en el botón **"+"** (arriba a la derecha) → **New repository**
4. Nombre: `presupuestos-app`
5. Descripción: "App de análisis de bajas estadísticas"
6. Selecciona **"Public"**
7. ✅ Marca "Add a README file"
8. Haz clic en **Create repository**
9. Haz clic en **Add file → Upload files**
10. Arrastra TODOS los archivos de tu carpeta `presupuestos` (EXCEPTO `__pycache__` y `.DS_Store`)
11. Escribe un mensaje: "Subir archivos de la app"
12. Haz clic en **Commit changes**

---

## ☁️ Paso 3: Desplegar en Streamlit Cloud (10 minutos)

1. **Ve a Streamlit Cloud:**
   - Abre [https://streamlit.io/cloud](https://streamlit.io/cloud)
   - Haz clic en **"Sign up"** (arriba a la derecha)
   - Selecciona **"Continue with GitHub"**
   - Autoriza a Streamlit para acceder a tu GitHub

2. **Crear nueva app:**
   - Haz clic en **"New app"** (botón grande o arriba a la derecha)
   - Verás 3 campos:
     - **Repository:** Selecciona `tu-usuario/presupuestos-app`
     - **Branch:** Deja `main`
     - **Main file path:** Escribe `analisis_mejorado.py` (o el archivo que quieras usar como principal)
   - Haz clic en **"Advanced settings..."** (abajo)

3. **Configurar credenciales (MUY IMPORTANTE):**
   - En la sección **"Secrets"**, pega este contenido:

   ```toml
   # Configuración de base de datos PostgreSQL
   [postgres]
   host = "195.154.137.88"
   database = "oclemconcursos"
   user = "metabase"
   password = "Oclem1010*"
   port = 55432

   # Configuración de base de datos MySQL
   [mysql]
   host = "ocleminformatica.com"
   database = "colossus_vgarcia"
   user = "colossus"
   password = "OIN2020p$j"
   port = 3306
   ```

4. **Desplegar:**
   - Haz clic en **"Deploy!"**
   - Espera 2-3 minutos mientras se instalan las dependencias
   - ¡Tu app estará lista!

5. **Hacer la app privada:**
   - Una vez desplegada, haz clic en **"Settings"** (arriba a la derecha)
   - Ve a la sección **"Sharing"**
   - En **"App visibility"**, selecciona **"Only specific people can view this app"**
   - Agrega tu email en **"Invite viewers"**
   - Haz clic en **"Save"**

---

## 📱 Paso 4: Acceder desde tu iPad

1. **Obtén la URL de tu app:**
   - En Streamlit Cloud, copia la URL de tu app (algo como: `https://tu-usuario-presupuestos-app-xxx.streamlit.app`)

2. **Abre Safari en tu iPad:**
   - Pega la URL
   - Inicia sesión con tu cuenta de Google/GitHub si te lo pide

3. **Crear icono en pantalla de inicio (opcional pero recomendado):**
   - Toca el botón **"Compartir"** (el cuadrado con flecha)
   - Selecciona **"Agregar a pantalla de inicio"**
   - Dale un nombre: "Análisis Bajas"
   - ¡Ahora tendrás un icono como si fuera una app nativa!

---

## 🔐 Seguridad

✅ **Tu app está protegida:**
- Solo las personas que autorices podrán acceder
- Las credenciales de base de datos están cifradas en Streamlit Cloud
- Nadie puede ver tu código ni tus datos

⚠️ **IMPORTANTE:**
- El archivo `.streamlit/secrets.toml` está en el `.gitignore` para que NUNCA se suba a GitHub
- Las credenciales solo están en Streamlit Cloud (de forma segura)

---

## ❓ Solución de problemas

### "La app no carga"
- Verifica que subiste TODOS los archivos a GitHub
- Verifica que el `requirements.txt` está incluido
- Revisa los logs en Streamlit Cloud (botón "Manage app" → "Logs")

### "Error de conexión a base de datos"
- Verifica que copiaste bien las credenciales en "Secrets"
- Asegúrate de que no hay espacios extra

### "No puedo acceder desde el iPad"
- Verifica que iniciaste sesión con la misma cuenta que autorizaste
- Comprueba que tienes conexión a internet

---

## 📞 ¿Necesitas ayuda?

Si algo no funciona, revisa:
1. Que todos los archivos están en GitHub
2. Que las credenciales en "Secrets" están correctas
3. Los logs de error en Streamlit Cloud

---

## 🎉 ¡Listo!

Ahora tienes tu aplicación funcionando en la nube, accesible desde tu iPad desde cualquier lugar, y de forma totalmente privada.

**URLs importantes:**
- Tu repositorio GitHub: `https://github.com/TU-USUARIO/presupuestos-app`
- Tu app Streamlit: `https://TU-USUARIO-presupuestos-app-xxx.streamlit.app`
- Panel de control: [https://streamlit.io/cloud](https://streamlit.io/cloud)
