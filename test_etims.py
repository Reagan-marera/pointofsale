import unittest
from flask import Flask
from models import db, Product, Sale, SaleItem, ETIMSConfig, User
from etims_service import ETIMSService
from datetime import datetime

class TestDigiTaxIntegration(unittest.TestCase):
    def setUp(self):
        # Set up an in-memory database for testing
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app.config['SECRET_KEY'] = 'testsecret'

        db.init_app(self.app)

        with self.app.app_context():
            db.create_all()

            # Create a test config
            config = ETIMSConfig(
                etims_enabled=True,
                etims_url='https://api.digitax.tech/ke/v2',
                etims_tin='2002720806',
                etims_bhf_id='00',
                etims_dvc_srl_no='DUMMY-API-KEY',
                etims_cmc_key='SIM-TEST-KEY',
                etims_is_sandbox=True
            )
            db.session.add(config)

            # Create a test user/cashier
            user = User(username='test_cashier', email='cashier@example.com', role='cashier')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

            # Create a test product
            product = Product(
                barcode='123456789012',
                name='Test Laptop',
                category='Electronics',
                buying_price=50000.0,
                selling_price=70000.0,
                current_stock=10,
                min_stock_level=2,
                vatable=True,
                etims_item_cls_code='5059690800',
                etims_tax_type='B'
            )
            db.session.add(product)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    def test_etims_config_defaults(self):
        with self.app.app_context():
            config = ETIMSConfig.query.first()
            self.assertIsNotNone(config)
            self.assertTrue(config.etims_enabled)
            self.assertEqual(config.etims_tin, '2002720806')

    def test_etims_device_initialization_simulated(self):
        with self.app.app_context():
            config = ETIMSConfig.query.first()
            result = ETIMSService.initialize_device(
                config_model=config,
                db_session=db.session,
                tin='DUMMY-TIN',
                bhf_id='00',
                dvc_srl_no='DUMMY-API-KEY',
                url='https://api.digitax.tech/ke/v2',
                is_sandbox=True
            )
            self.assertTrue(result['success'])
            self.assertTrue(result['cmc_key'].startswith('SIM-'))
            self.assertEqual(config.etims_cmc_key, result['cmc_key'])

    def test_etims_product_registration_simulated(self):
        with self.app.app_context():
            config = ETIMSConfig.query.first()
            product = Product.query.first()
            result = ETIMSService.register_product(config, product)
            self.assertTrue(result['success'])
            self.assertEqual(product.etims_item_code, 'KE1123456789012')

    def test_etims_sale_submission_simulated(self):
        with self.app.app_context():
            config = ETIMSConfig.query.first()
            user = User.query.first()
            product = Product.query.first()

            # Create a sale
            sale = Sale(
                receipt_number='IMO-20260101-0001',
                user_id=user.id,
                subtotal=70000.0,
                tax_amount=11200.0,
                total_amount=81200.0,
                payment_method='cash'
            )
            db.session.add(sale)
            db.session.commit()

            # Create sale item
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=1,
                unit_price=70000.0,
                total_price=70000.0
            )
            db.session.add(sale_item)
            db.session.commit()

            result = ETIMSService.submit_sale(config, sale, 'test_cashier')
            self.assertTrue(result['success'])
            self.assertIsNotNone(result['rcpt_no'])
            self.assertIsNotNone(result['rcpt_sign'])
            self.assertIsNotNone(result['intrl_data'])

    def test_etims_sale_submission_digitax_payload_pricing(self):
        from unittest.mock import patch, MagicMock
        with self.app.app_context():
            config = ETIMSConfig.query.first()
            # Set provider to DIGITAX explicitly
            config.etims_provider = 'DIGITAX'
            # Change cmc_key so it doesn't trigger mock/simulated check
            config.etims_cmc_key = 'REAL-API-KEY-123'
            config.etims_url = 'https://api.digitax.tech/ke/v2'

            user = User.query.first()
            product = Product.query.first() # Vatable laptop selling_price=70000.0, vatable=True

            sale = Sale(
                receipt_number='IMO-20260101-0002',
                user_id=user.id,
                subtotal=70000.0,
                tax_amount=11200.0,
                total_amount=81200.0,
                payment_method='cash'
            )
            db.session.add(sale)
            db.session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=1.5, # Let's test decimal quantity
                unit_price=300.0,
                total_price=450.0
            )
            db.session.add(sale_item)
            db.session.commit()

            # Mock requests.post
            with patch('requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "invoice_number": "DGTX-INV-1234",
                    "receipt_number": "DGTX-RCPT-1234",
                    "internal_data": "DGTX-INTRL-1234",
                    "receipt_signature": "DGTX-SIGN-1234"
                }
                mock_post.return_value = mock_response

                result = ETIMSService.submit_sale(config, sale, 'test_cashier')

                # Check that requests.post was called
                mock_post.assert_called_once()
                args, kwargs = mock_post.call_args
                payload = kwargs.get('json', {})

                # Verify payload item fields match DigiTax's mathematical rules
                items = payload.get('items', [])
                self.assertEqual(len(items), 1)
                item_payload = items[0]

                # unit_price = round(300.0 * 1.16, 2) = 348.0
                # total_amount = round(1.5 * 348.0, 2) = 522.0
                # taxable_amount = round(450.0, 2) = 450.0
                # tax_amount = round(522.0 - 450.0, 2) = 72.0
                self.assertEqual(item_payload['quantity'], 1.5)
                self.assertEqual(item_payload['unit_price'], 348.0)
                self.assertEqual(item_payload['total_amount'], 522.0)
                self.assertEqual(item_payload['taxable_amount'], 450.0)
                self.assertEqual(item_payload['tax_amount'], 72.0)
                self.assertEqual(item_payload['unit_price'] * item_payload['quantity'], item_payload['total_amount'])

                self.assertTrue(result['success'])
                self.assertEqual(result['invc_no'], 'DGTX-INV-1234')

if __name__ == '__main__':
    unittest.main()
