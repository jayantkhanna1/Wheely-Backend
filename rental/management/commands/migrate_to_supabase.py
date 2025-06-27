from django.core.management.base import BaseCommand
from django.db import connection
from rental.supabase_client import get_supabase_client
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrate existing data to Supabase and create necessary RLS policies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-policies',
            action='store_true',
            help='Create RLS policies for tables',
        )
        parser.add_argument(
            '--create-storage-bucket',
            action='store_true',
            help='Create storage bucket for file uploads',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Supabase migration...'))
        
        try:
            supabase = get_supabase_client()
            
            if options['create_storage_bucket']:
                self.create_storage_bucket(supabase)
            
            if options['create_policies']:
                self.create_rls_policies(supabase)
            
            self.stdout.write(self.style.SUCCESS('Migration completed successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Migration failed: {str(e)}'))
            logger.error(f'Migration error: {str(e)}')

    def create_storage_bucket(self, supabase):
        """Create storage bucket for file uploads"""
        try:
            bucket_name = 'wheely-uploads'
            
            # Create bucket
            response = supabase.storage.create_bucket(bucket_name, {
                'public': True,
                'allowedMimeTypes': [
                    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                    'application/pdf', 'application/msword',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                ],
                'fileSizeLimit': 10485760  # 10MB
            })
            
            self.stdout.write(self.style.SUCCESS(f'Storage bucket "{bucket_name}" created successfully'))
            
        except Exception as e:
            if 'already exists' in str(e).lower():
                self.stdout.write(self.style.WARNING(f'Storage bucket already exists'))
            else:
                self.stdout.write(self.style.ERROR(f'Failed to create storage bucket: {str(e)}'))

    def create_rls_policies(self, supabase):
        """Create Row Level Security policies"""
        policies = [
            # Users table policies
            {
                'table': 'rental_user',
                'policy_name': 'Users can read own data',
                'sql': '''
                CREATE POLICY "Users can read own data" ON rental_user
                FOR SELECT USING (auth.uid()::text = private_token::text);
                '''
            },
            {
                'table': 'rental_user',
                'policy_name': 'Users can update own data',
                'sql': '''
                CREATE POLICY "Users can update own data" ON rental_user
                FOR UPDATE USING (auth.uid()::text = private_token::text);
                '''
            },
            
            # Vehicles table policies
            {
                'table': 'rental_vehicle',
                'policy_name': 'Anyone can read verified vehicles',
                'sql': '''
                CREATE POLICY "Anyone can read verified vehicles" ON rental_vehicle
                FOR SELECT USING (is_verified = true AND is_available = true);
                '''
            },
            {
                'table': 'rental_vehicle',
                'policy_name': 'Owners can manage their vehicles',
                'sql': '''
                CREATE POLICY "Owners can manage their vehicles" ON rental_vehicle
                FOR ALL USING (
                    EXISTS (
                        SELECT 1 FROM rental_user 
                        WHERE rental_user.id = rental_vehicle.owner_id 
                        AND auth.uid()::text = rental_user.private_token::text
                    )
                );
                '''
            },
            
            # Reviews table policies
            {
                'table': 'rental_review',
                'policy_name': 'Anyone can read reviews',
                'sql': '''
                CREATE POLICY "Anyone can read reviews" ON rental_review
                FOR SELECT USING (true);
                '''
            },
            {
                'table': 'rental_review',
                'policy_name': 'Users can create reviews',
                'sql': '''
                CREATE POLICY "Users can create reviews" ON rental_review
                FOR INSERT WITH CHECK (
                    EXISTS (
                        SELECT 1 FROM rental_user 
                        WHERE rental_user.id = rental_review.user_id 
                        AND auth.uid()::text = rental_user.private_token::text
                    )
                );
                '''
            },
            
            # Rides table policies
            {
                'table': 'rental_ride',
                'policy_name': 'Users can read own rides',
                'sql': '''
                CREATE POLICY "Users can read own rides" ON rental_ride
                FOR SELECT USING (
                    EXISTS (
                        SELECT 1 FROM rental_user 
                        WHERE rental_user.id = rental_ride.user_id 
                        AND auth.uid()::text = rental_user.private_token::text
                    )
                );
                '''
            },
        ]
        
        for policy in policies:
            try:
                # First enable RLS on the table
                enable_rls_sql = f"ALTER TABLE {policy['table']} ENABLE ROW LEVEL SECURITY;"
                supabase.rpc('exec_sql', {'sql': enable_rls_sql})
                
                # Then create the policy
                supabase.rpc('exec_sql', {'sql': policy['sql']})
                
                self.stdout.write(
                    self.style.SUCCESS(f'Created policy "{policy["policy_name"]}" for {policy["table"]}')
                )
                
            except Exception as e:
                if 'already exists' in str(e).lower():
                    self.stdout.write(
                        self.style.WARNING(f'Policy "{policy["policy_name"]}" already exists')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to create policy "{policy["policy_name"]}": {str(e)}')
                    )