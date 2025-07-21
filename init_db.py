from app import app, db, Patient

def migrate_add_route_order():
    """Add route_order column if it doesn't exist"""
    try:
        # Try to add the column using raw SQL
        with db.engine.connect() as conn:
            # Check if column exists first
            result = conn.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='patients' AND column_name='route_order'
            """)
            
            if not result.fetchone():
                print("🔄 Adding route_order column...")
                conn.execute("ALTER TABLE patients ADD COLUMN route_order INTEGER")
                conn.commit()
                print("✅ route_order column added successfully!")
            else:
                print("✅ route_order column already exists.")
                
    except Exception as e:
        print(f"⚠️  Could not add route_order column: {e}")
        print("💡 This might be expected if the column already exists")

# Ensure database operations happen within the app context
with app.app_context():
    # Create all tables (this will create new tables but won't modify existing ones)
    db.create_all()
    print("✅ Database tables created/verified!")
    
    # Add the new column to existing tables
    migrate_add_route_order()
    
    print("✅ PostgreSQL database initialized successfully!")
