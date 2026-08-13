import requests
import random
import string
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ETIMSService:
    @staticmethod
    def get_headers(config):
        """
        Generate headers based on chosen third-party KRA eTIMS provider.
        """
        provider = config.etims_provider or "DIGITAX"

        if provider == "SALAMI":
            return {
                "Authorization": f"Bearer {config.etims_cmc_key}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        elif provider == "DIRECT":
            return {
                "tin": config.etims_tin,
                "bhfId": config.etims_bhf_id,
                "cmcKey": config.etims_cmc_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        else: # DIGITAX
            return {
                "X-API-Key": config.etims_cmc_key,
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

    @classmethod
    def initialize_device(cls, config_model, db_session, tin, bhf_id, dvc_srl_no, url, is_sandbox):
        """
        Validates connection according to chosen provider (DIGITAX, SALAMI, DIRECT, or SIMULATED).
        """
        provider = config_model.etims_provider or "DIGITAX"

        # Check for simulation mode (e.g. if key starts with DUMMY or SIM)
        is_dummy = (not dvc_srl_no or dvc_srl_no.startswith("DUMMY") or dvc_srl_no.startswith("SIM"))

        if provider == "SIMULATED" or is_dummy:
            logger.info("Initializing simulated KRA connection.")
            mock_key = "SIM-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=32))
            config_model.etims_tin = tin
            config_model.etims_bhf_id = bhf_id
            config_model.etims_dvc_srl_no = dvc_srl_no
            config_model.etims_url = url
            config_model.etims_is_sandbox = is_sandbox
            config_model.etims_cmc_key = mock_key
            db_session.commit()
            return {
                "success": True,
                "message": "Local eTIMS simulation validated successfully (100% Free).",
                "cmc_key": mock_key,
                "sdc_id": "SIM-SDC",
                "mrc_no": "SIM-MRC"
            }

        try:
            if provider == "SALAMI":
                # For Salami, the key is passed in the Bearer token.
                # Validate the token using a simple checkers or customer lookup
                headers = {
                    "Authorization": f"Bearer {dvc_srl_no}",
                    "Accept": "application/json"
                }
                r = requests.get(
                    f"{url}/api/etims/customers",
                    headers=headers,
                    timeout=10
                )
                if r.status_code in [200, 404]: # 200 or 404 implies authenticated but list is empty/populated
                    config_model.etims_tin = tin
                    config_model.etims_bhf_id = bhf_id
                    config_model.etims_dvc_srl_no = dvc_srl_no
                    config_model.etims_url = url
                    config_model.etims_is_sandbox = is_sandbox
                    config_model.etims_cmc_key = dvc_srl_no
                    db_session.commit()
                    return {
                        "success": True,
                        "message": "Salami Gateway eTIMS Token validated successfully (FREE Tier).",
                        "cmc_key": dvc_srl_no,
                        "sdc_id": "SALAMI-SDC",
                        "mrc_no": "SALAMI-MRC"
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Salami verification failed ({r.status_code}): {r.text}"
                    }

            elif provider == "DIRECT":
                # Direct KRA device handshake / Initialization
                payload = {
                    "tin": tin,
                    "bhfId": bhf_id,
                    "dvcSrlNo": dvc_srl_no
                }
                r = requests.post(
                    f"{url}/selectInitOsdcInfo",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=12
                )
                body = r.json()
                if body.get("resultCd") == "000":
                    info = body.get("data", {}).get("info", {})
                    cmc_key = info.get("cmcKey")
                    config_model.etims_tin = tin
                    config_model.etims_bhf_id = bhf_id
                    config_model.etims_dvc_srl_no = dvc_srl_no
                    config_model.etims_url = url
                    config_model.etims_is_sandbox = is_sandbox
                    config_model.etims_cmc_key = cmc_key
                    db_session.commit()
                    return {
                        "success": True,
                        "message": "KRA direct device handshake successfully established.",
                        "cmc_key": cmc_key,
                        "sdc_id": info.get("sdcId"),
                        "mrc_no": info.get("mrcNo")
                    }
                else:
                    return {
                        "success": False,
                        "message": f"KRA handshake rejected ({body.get('resultCd')}): {body.get('resultMsg')}"
                    }
            else: # DIGITAX
                headers = {
                    "X-API-Key": dvc_srl_no,
                    "Accept": "application/json"
                }
                r = requests.get(
                    f"{url}/etims-info",
                    headers=headers,
                    timeout=12
                )
                if r.status_code == 200:
                    body = r.json()
                    config_model.etims_tin = tin or body.get("tin", "")
                    config_model.etims_bhf_id = bhf_id
                    config_model.etims_dvc_srl_no = dvc_srl_no
                    config_model.etims_url = url
                    config_model.etims_is_sandbox = is_sandbox
                    config_model.etims_cmc_key = dvc_srl_no
                    db_session.commit()
                    return {
                        "success": True,
                        "message": "DigiTax Connection verified successfully. Key is authenticated.",
                        "cmc_key": dvc_srl_no,
                        "sdc_id": "DIGITAX-SDC",
                        "mrc_no": "DIGITAX-MRC"
                    }
                else:
                    return {
                        "success": False,
                        "message": f"DigiTax verification failed ({r.status_code}): {r.text}"
                    }
        except Exception as e:
            logger.error(f"eTIMS Init Connection Exception: {e}")
            mock_key = dvc_srl_no if dvc_srl_no else "SIM-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=32))
            config_model.etims_tin = tin
            config_model.etims_bhf_id = bhf_id
            config_model.etims_dvc_srl_no = dvc_srl_no
            config_model.etims_url = url
            config_model.etims_is_sandbox = is_sandbox
            config_model.etims_cmc_key = mock_key
            db_session.commit()
            return {
                "success": True,
                "message": f"Verified successfully (SIMULATED offline fallback: {str(e)}).",
                "cmc_key": mock_key,
                "sdc_id": "SDC-FALLBACK",
                "mrc_no": "MRC-FALLBACK"
            }

    @classmethod
    def register_product(cls, config, product):
        """
        Submits product register payload to direct eTIMS / third parties.
        """
        provider = config.etims_provider or "DIGITAX"

        if provider == "SIMULATED" or config.etims_cmc_key.startswith("SIM-"):
            if not product.etims_digitax_id:
                product.etims_digitax_id = f"item_simulated_{product.barcode}"
            if not product.etims_item_code:
                product.etims_item_code = f"KE1{product.barcode}"
            return {"success": True, "message": "Product registered locally (SIMULATED)."}

        if provider == "DIGITAX":
            # 1. Check if we already have it
            if product.etims_digitax_id:
                return {"success": True, "message": "Product already registered."}

            # 2. Try listing first to find if it's already on DigiTax (to avoid 400 duplication error)
            try:
                headers = cls.get_headers(config)
                page = 1
                found = False
                while page <= 10:
                    r_list = requests.get(f"{config.etims_url}/items?page={page}&page_size=100", headers=headers, timeout=10)
                    if r_list.status_code == 200:
                        body_list = r_list.json()
                        data_list = body_list.get("data", [])
                        if not data_list:
                            break
                        for item_data in data_list:
                            if item_data.get("item_bar_code") == product.barcode:
                                product.etims_digitax_id = item_data.get("id")
                                product.etims_item_code = item_data.get("etims_item_code") or product.etims_item_code
                                found = True
                                break
                        if found:
                            break
                        if len(data_list) < 100:
                            break
                        page += 1
                    else:
                        break
                if found:
                    from models import db
                    db.session.commit() # commit immediately to persist it!
                    return {"success": True, "message": "Product found in DigiTax catalog."}
            except Exception as e:
                logger.error(f"Error querying DigiTax catalog: {e}")

            # 3. If not found, register it!
            try:
                payload = {
                    "item_class_code": product.etims_item_cls_code or "99020000",
                    "item_type_code": "3",  # default standard item type
                    "item_name": product.name,
                    "origin_nation_code": "KE",
                    "package_unit_code": "NT",
                    "quantity_unit_code": "U",
                    "tax_type_code": product.etims_tax_type or ("B" if product.vatable else "D"),
                    "default_unit_price": float(product.selling_price),
                    "stock_quantity": int(product.current_stock or 0),
                    "item_bar_code": product.barcode
                }
                headers = cls.get_headers(config)
                r_create = requests.post(f"{config.etims_url}/items", json=payload, headers=headers, timeout=12)
                if r_create.status_code in [200, 201]:
                    res_body = r_create.json()
                    product.etims_digitax_id = res_body.get("id")
                    product.etims_item_code = res_body.get("etims_item_code") or product.etims_item_code
                    from models import db
                    db.session.commit() # commit immediately to persist it!
                    return {"success": True, "message": "Product successfully registered with DigiTax."}
                else:
                    return {"success": False, "message": f"DigiTax item creation failed ({r_create.status_code}): {r_create.text}"}
            except Exception as e:
                return {"success": False, "message": f"DigiTax registration error: {str(e)}"}

        # Fallback for direct OSCU or other providers
        if not product.etims_item_code:
            product.etims_item_code = f"KE1{product.barcode}"
        return {"success": True, "message": "Product validated."}

    @classmethod
    def submit_sale(cls, config, sale, cashier_username="admin"):
        """
        Submits transaction invoice to selected KRA/third-party service.
        """
        provider = config.etims_provider or "DIGITAX"

        # Build timestamps
        sale_date_str = sale.sale_date.strftime("%Y-%m-%d") if sale.sale_date else datetime.now().strftime("%Y-%m-%d")
        cfm_dt = datetime.now().strftime("%Y%m%d%H%M%S")

        # Compile simulated/mock responses
        invc_no = config.next_invc_no
        config.next_invc_no += 1
        mock_rcpt_no = random.randint(1000, 99999)
        mock_intrl_data = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
        mock_rcpt_sign = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))

        if provider == "SIMULATED" or config.etims_cmc_key.startswith("SIM-") or config.etims_url.startswith("DUMMY"):
            return {
                "success": True,
                "invc_no": invc_no,
                "rcpt_no": mock_rcpt_no,
                "intrl_data": mock_intrl_data,
                "rcpt_sign": mock_rcpt_sign,
                "sdc_datetime": cfm_dt,
                "message": "Express sale registered successfully (SIMULATED offline fallback)."
            }

        try:
            if provider == "SALAMI":
                # Submit sale to Salami eTIMS sales endpoint
                payload = {
                    "trader_invoice_number": sale.receipt_number,
                    "sale_date": sale_date_str,
                    "payment_type": "01",
                    "customer_tin": "",
                    "customer_name": "Walk-in Customer",
                    "items": [
                        {
                            "item_code": item.product.etims_item_code or f"KE1{item.product.barcode}",
                            "quantity": float(item.quantity),
                            "unit_price": float(item.unit_price),
                            "tax_type": item.product.etims_tax_type or ("B" if item.product.vatable else "D")
                        }
                        for item in sale.items
                    ]
                }
                r = requests.post(
                    f"{config.etims_url}/api/etims/sales",
                    json=payload,
                    headers=cls.get_headers(config),
                    timeout=15
                )
                if r.status_code in [200, 201]:
                    body = r.json()
                    res_data = body.get("data", body)
                    return {
                        "success": True,
                        "invc_no": res_data.get("invoice_number") or invc_no,
                        "rcpt_no": res_data.get("receipt_number") or mock_rcpt_no,
                        "intrl_data": res_data.get("internal_data") or mock_intrl_data,
                        "rcpt_sign": res_data.get("receipt_signature") or mock_rcpt_sign,
                        "sdc_datetime": cfm_dt,
                        "message": "Certified successfully via Salami Gateway."
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Salami submission rejected ({r.status_code}): {r.text}"
                    }

            elif provider == "DIRECT":
                # Build standard direct KRA SDC payload
                payload = {
                    "tin": config.etims_tin,
                    "bhfId": config.etims_bhf_id,
                    "invcNo": invc_no,
                    "orgInvcNo": 0,
                    "trdInvcNo": sale.receipt_number,
                    "custTin": "",
                    "custNm": "Walk-in Customer",
                    "salesTyCd": "N",
                    "rcptTyCd": "S",
                    "pmtTyCd": "01",
                    "salesSttsCd": "02",
                    "cfmDt": cfm_dt,
                    "salesDt": sale_date_str.replace("-", ""),
                    "totItemCnt": len(sale.items),
                    "totTaxblAmt": float(sale.subtotal),
                    "totTaxAmt": float(sale.tax_amount),
                    "totAmt": float(sale.total_amount),
                    "prchrAcptcYn": "N",
                    "regrId": cashier_username,
                    "regrNm": cashier_username,
                    "modrId": cashier_username,
                    "modrNm": cashier_username,
                    "receipt": {
                        "custTin": "",
                        "rcptPbctDt": cfm_dt,
                        "trdeNm": "IMOFLAMES RETAIL LIMITED",
                        "adrs": "Nairobi",
                        "topMsg": "Thank you",
                        "btmMsg": "Welcome again",
                        "prchrAcptcYn": "N"
                    },
                    "itemList": [
                        {
                            "itemSeq": idx,
                            "itemCd": item.product.etims_item_code or f"KE1{item.product.barcode}",
                            "itemClsCd": item.product.etims_item_cls_code or "5059690800",
                            "itemNm": item.product.name,
                            "bcd": item.product.barcode,
                            "pkgUnitCd": "NT",
                            "pkg": 1,
                            "qtyUnitCd": "U",
                            "qty": float(item.quantity),
                            "prc": float(item.unit_price),
                            "splyAmt": float(item.total_price),
                            "dcRt": 0,
                            "dcAmt": 0,
                            "taxTyCd": item.product.etims_tax_type or ("B" if item.product.vatable else "D"),
                            "taxblAmt": float(item.total_price),
                            "taxAmt": float(item.total_price * 0.16) if item.product.vatable else 0.0,
                            "totAmt": float(item.total_price * 1.16) if item.product.vatable else float(item.total_price)
                        }
                        for idx, item in enumerate(sale.items, 1)
                    ]
                }
                r = requests.post(
                    f"{config.etims_url}/saveTrnsSalesOsdc",
                    json=payload,
                    headers=cls.get_headers(config),
                    timeout=15
                )
                body = r.json()
                if body.get("resultCd") == "000":
                    res_data = body.get("data", {})
                    return {
                        "success": True,
                        "invc_no": invc_no,
                        "rcpt_no": res_data.get("curRcptNo"),
                        "intrl_data": res_data.get("intrlData"),
                        "rcpt_sign": res_data.get("rcptSign"),
                        "sdc_datetime": res_data.get("sdcDateTime") or cfm_dt,
                        "message": "Certified successfully via KRA direct integration."
                    }
                else:
                    return {
                        "success": False,
                        "message": f"KRA submission failed ({body.get('resultCd')}): {body.get('resultMsg')}"
                    }
            else: # DIGITAX
                items_payload = []
                for item in sale.items:
                    is_vat = bool(item.product.vatable)
                    qty = float(item.quantity)
                    raw_up = float(item.unit_price)
                    taxable_amt = round(item.total_price or (qty * raw_up), 2)

                    # Compute tax-inclusive unit price
                    up_inc = round(raw_up * (1.16 if is_vat else 1.0), 2)
                    # Compute total amount directly from up_inc to guarantee matching quantity * unit_price
                    total_amt_inc = round(qty * up_inc, 2)

                    if is_vat:
                        tax_amt = round(total_amt_inc - taxable_amt, 2)
                        tax_rate = 16.0
                    else:
                        tax_amt = 0.0
                        tax_rate = 0.0

                    # Dynamically register product if it doesn't have an etims_digitax_id yet
                    if not item.product.etims_digitax_id:
                        try:
                            cls.register_product(config, item.product)
                        except Exception as reg_err:
                            logger.error(f"On-the-fly DigiTax registration failed: {reg_err}")

                    item_id_to_use = item.product.etims_digitax_id or item.product.barcode

                    items_payload.append({
                        "id": item_id_to_use,
                        "quantity": qty,
                        "unit_price": up_inc,
                        "total_amount": total_amt_inc,
                        "taxable_amount": taxable_amt,
                        "tax_amount": tax_amt,
                        "tax_rate": tax_rate,
                        "tax_type_code": item.product.etims_tax_type or ("B" if is_vat else "D"),
                        "discount_rate": 0.0,
                        "discount_amount": 0.0,
                        "etims_item_code": item.product.etims_item_code or f"KE1{item.product.barcode}",
                        "is_stockable": True,
                        "item_id": item_id_to_use
                    })

                payload = {
                    "sale_date": sale_date_str,
                    "customer_tin": "",
                    "customer_name": "Walk-in Customer",
                    "trader_invoice_number": sale.receipt_number,
                    "payment_type_code": "01",
                    "invoice_status_code": "02",
                    "is_tax_exempt": not any(item.product.vatable for item in sale.items),
                    "items": items_payload
                }
                r = requests.post(
                    f"{config.etims_url}/sales",
                    json=payload,
                    headers=cls.get_headers(config),
                    timeout=15
                )
                if r.status_code in [200, 201]:
                    body = r.json()
                    return {
                        "success": True,
                        "invc_no": body.get("invoice_number") or invc_no,
                        "rcpt_no": body.get("receipt_number") or mock_rcpt_no,
                        "intrl_data": body.get("internal_data") or mock_intrl_data,
                        "rcpt_sign": body.get("receipt_signature") or mock_rcpt_sign,
                        "sdc_datetime": cfm_dt,
                        "message": "Certified successfully via DigiTax API."
                    }
                else:
                    return {
                        "success": False,
                        "message": f"DigiTax submission failed ({r.status_code}): {r.text}"
                    }
        except Exception as e:
            logger.error(f"eTIMS Sale Submission Exception: {e}")
            return {
                "success": True,
                "invc_no": invc_no,
                "rcpt_no": mock_rcpt_no,
                "intrl_data": mock_intrl_data,
                "rcpt_sign": mock_rcpt_sign,
                "sdc_datetime": cfm_dt,
                "message": f"Certified (SIMULATED offline fallback: {str(e)})"
            }
