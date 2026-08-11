import unittest
from flask import Flask
from models import db, Product, Sale, SaleItem, ETIMSConfig, User
from etims_service import ETIMSService
from datetime import datetime

class TestETIMSIntegration(unittest.TestCase):
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
                etims_url='https://etims-api-sbx.kra.go.ke/etims-api',
                etims_tin='P000000045R',
                etims_bhf_id='00',
                etims_dvc_srl_no='TEST-SERIAL',
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
            self.assertEqual(config.etims_tin, 'P000000045R')

    def test_etims_device_initialization_simulated(self):
        with self.app.app_context():
            config = ETIMSConfig.query.first()
            result = ETIMSService.initialize_device(
                config_model=config,
                db_session=db.session,
                tin='DUMMY-TIN',
                bhf_id='00',
                dvc_srl_no='DUMMY-SERIAL',
                url='https://etims-api-sbx.kra.go.ke/etims-api',
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

if __name__ == '__main__':
    unittest.main()
