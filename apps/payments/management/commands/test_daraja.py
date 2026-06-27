"""
Test Daraja API functions in isolation

Usage:
    python manage.py test_daraja --function get_access_token
    python manage.py test_daraja --function stk_push --phone 254712345678 --amount 100
"""

from django.core.management.base import BaseCommand

from apps.payments.daraja import get_access_token, initiate_stk_push


class Command(BaseCommand):
    help = "Test Daraja API functions in isolation"

    def add_arguments(self, parser):
        parser.add_argument(
            '--function',
            type=str,
            required=True,
            choices=['get_access_token', 'stk_push'],
            help='Daraja function to test'
        )
        parser.add_argument('--phone', type=str, help='Phone number for STK push (254XXXXXXXXX)')
        parser.add_argument('--amount', type=int, help='Amount in KES')
        parser.add_argument('--reference', type=str, default='TEST', help='Account reference')

    def handle(self, *args, **options):
        function_name = options['function']

        if function_name == 'get_access_token':
            self.test_access_token()
        elif function_name == 'stk_push':
            self.test_stk_push(options)

    def test_access_token(self):
        """Test getting M-Pesa access token"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.WARNING("Testing: get_access_token()"))
        self.stdout.write("="*60 + "\n")

        try:
            access_token = get_access_token()

            if access_token:
                self.stdout.write(self.style.SUCCESS("✓ Access token retrieved successfully\n"))
                self.stdout.write(f"Token (first 20 chars): {access_token[:20]}...")
                self.stdout.write(f"Token length: {len(access_token)} characters")
                self.stdout.write(f"\nFull token:\n{access_token}")

                # Save to file for easy copying
                with open('/tmp/daraja_access_token.txt', 'w') as f:
                    f.write(access_token)
                self.stdout.write(
                    self.style.SUCCESS("\n✓ Token saved to /tmp/daraja_access_token.txt")
                )
            else:
                self.stdout.write(self.style.ERROR("✗ Failed to retrieve access token"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc())

    def test_stk_push(self, options):
        """Test STK push with provided parameters"""
        phone = options.get('phone')
        amount = options.get('amount')
        reference = options.get('reference', 'TEST')

        if not phone or not amount:
            self.stdout.write(
                self.style.ERROR("Error: --phone and --amount are required for stk_push")
            )
            return

        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.WARNING("Testing: initiate_stk_push()"))
        self.stdout.write("="*60 + "\n")
        self.stdout.write(f"Phone: {phone}")
        self.stdout.write(f"Amount: KES {amount}")
        self.stdout.write(f"Reference: {reference}\n")

        try:
            # Get access token first
            self.stdout.write("Step 1: Getting access token...")
            access_token = get_access_token()
            if not access_token:
                self.stdout.write(self.style.ERROR("✗ Failed to get access token"))
                return
            self.stdout.write(self.style.SUCCESS("✓ Access token retrieved\n"))

            # Initiate STK push
            self.stdout.write("Step 2: Initiating STK push...")
            response = initiate_stk_push(
                phone_number=phone,
                amount=amount,
                account_reference=reference,
                transaction_desc=f"Test payment {reference}"
            )

            if response:
                self.stdout.write(self.style.SUCCESS("✓ STK push initiated successfully\n"))
                self.stdout.write("Response:")
                import json
                self.stdout.write(json.dumps(response, indent=2))
            else:
                self.stdout.write(self.style.ERROR("✗ STK push failed"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc())
