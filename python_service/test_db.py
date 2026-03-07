import psycopg


url= "postgresql://postgres:Sevk%2A310522260399@db.ndbhpjxjrlwiwdtwrrlg.supabase.co:6543/postgres"

try:
    conn = psycopg.connect(url, sslmode='require')
    print('✅ Connected!')
    conn.close()
except Exception as e:
    print(f'❌ Failed: {e}')