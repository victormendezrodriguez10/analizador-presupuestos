#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='195.154.137.88',
    port=55432,
    user='metabase',
    password='Oclem1010*',
    database='oclemconcursos'
)

cursor = conn.cursor()

# Ver todas las tablas
cursor.execute("""
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY tablename;
""")
tables = cursor.fetchall()
print("📋 Tablas disponibles:")
for table in tables:
    print(f"  - {table[0]}")

# Verificar si existe adjudicaciones_metabase o adjudicaciones
cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name LIKE '%adjudicacion%';
""")
adj_tables = cursor.fetchall()
print("\n🔍 Tablas relacionadas con 'adjudicacion':")
for table in adj_tables:
    print(f"  ✓ {table[0]}")

    # Ver estructura de la tabla
    cursor.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table[0]}'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()
    print(f"    Columnas: {len(columns)}")
    for col in columns[:10]:  # Primeras 10 columnas
        print(f"      - {col[0]} ({col[1]})")

    # Contar registros
    cursor.execute(f"SELECT COUNT(*) FROM {table[0]};")
    count = cursor.fetchone()[0]
    print(f"    Registros: {count:,}\n")

cursor.close()
conn.close()
