from .clients.Client import SyncClient
from .utils.response_models import PaymentStatus, OrderStatus

class SyncOxaPay:
    def __init__(self, merchant_api_key: str, sandbox: bool = False):
        """
        :param merchant_api_key: The merchant's API key for authentication
        :param sandbox: Whether to use the sandbox environment. Defaults to False.
        """
        self.merchant_api_key = merchant_api_key
        self.sandbox = sandbox
        self.client = SyncClient()

    def check_api_status(self):
        """
        Checks the current status of the OxaPay API
        :return: The API status information
        """
        try:
            return self.client.request('POST', 'monitor')
        except Exception:
            raise Exception

    def create_invoice(
            self,
            amount: float,
            currency: str = None,
            callbackUrl: str = None,
            underPaidCover: float = None,
            feePaidByPayer: float = 0,  # default 0
            lifeTime: int = 60,  # default 60
            email: str = None,
            orderId: str = None,
            description: str = None,
            returnUrl: str = None,
            raw_response: bool = False  # Flag to request a raw response
    ):
        """
        :param amount: The amount for the payment
        :param currency: The currency symbol. Defaults to None(USD)
        :param callbackUrl: The URL where payment information will be sent. Defaults to None
        :param underPaidCover: The acceptable inaccuracy in payment. Defaults to None
        :param feePaidByPayer: Whether the payer will cover the invoice commission. 1 indicates that the payer will pay the fee, while 0 indicates that the merchant will pay the fee. Default: Merchant setting.
        :param lifeTime: The expiration time for the payment link in minutes. Defaults to 60.
        :param email: The payer's email address. Defaults to None.
        :param orderId: The unique order ID. Defaults to None.
        :param description: The order details. Defaults to None.
        :param returnUrl: The URL for redirecting after a successful payment. Defaults to None.
        :param raw_response: Flag to request a raw response. Defaults to False.
        :return: The OrderStatus object or an error message.
        """
        if amount >= 1000000:
            print('da')
            raise ValueError("amount must be <= 1000000")
        if feePaidByPayer not in {0, 1}:
            raise ValueError("feePaidByPayer should be either 0 or 1")
        if not 15 <= lifeTime <= 2880:
            raise ValueError("lifeTime should be between 15 and 2880")

        merchant = 'sandbox' if self.sandbox else self.merchant_api_key
        invoice_data = {
            'merchant': merchant,
            'amount': amount,
            'currency': currency,
            'callbackUrl': callbackUrl,
            'underPaidCover': underPaidCover,
            'feePaidByPayer': feePaidByPayer,
            'lifeTime': lifeTime,
            'email': email,
            'orderId': orderId,
            'description': description,
            'returnUrl': returnUrl
        }
        try:
            response_data = self.client.request('POST', 'merchants/request', json_data=invoice_data)
            if raw_response:
                return response_data
            elif response_data.get('result') == 100:  # Successful response
                return OrderStatus(**response_data)
            else:  # Error response
                return f"Error: {response_data.get('message', 'Unknown error')}"
        except Exception as e:
            raise Exception(f"Error creating invoice: {e}")

    def get_supported_currencies(self):
        """
        Retrieves a list of supported currencies and their network details.
        :return: A list of supported currencies with their details.
        """
        try:
            return self.client.request('POST', 'api/currencies')
        except Exception:
            raise Exception

    def get_supported_networks(self):
        """
        Retrieves a list of supported blockchain networks for cryptocurrency transactions.

        :return: A list of supported blockchain networks.
        """
        try:
            return self.client.request('POST', 'api/networks')
        except Exception:
            raise Exception

    def get_supported_fiat_currencies(self):
        """
        Retrieves a list of supported fiat currencies and their details.

        :return: A list of supported fiat currencies with their details.
        """
        try:
            return self.client.request('POST', 'api/fiats')
        except Exception:
            raise Exception

    def get_payment_information(self, trackId: int, raw_response: bool = False):
        """
        Retrieves the details of a specific payment by its TrackId.

        :param trackId: The TrackId of the payment.
        :param raw_response: Flag to request a raw response. Defaults to False.
        :return: The PaymentStatus object or raw response.
        """
        merchant = 'sandbox' if self.sandbox else self.merchant_api_key
        payment_data = {
            'merchant': merchant,
            'trackId': trackId
        }
        try:
            response_data = self.client.request('POST', 'merchants/inquiry', json_data=payment_data)
            if raw_response:
                return response_data
            else:
                return PaymentStatus(**response_data)
        except Exception:
            raise Exception

    def create_white_label_payment(
            self,
            amount: float,
            payCurrency: str,
            callbackUrl: str = None,
            payAmount: float = None,
            currency: str = None,
            email: str = None,
            orderId: str = None,
            description: str = None,
            underPaidCover: float = None,
            feePaidByPayer: float = None,
            lifeTime: int = None,
            network: str = None
    ):
        """
        Creates a white-label payment.

        :param amount: The amount for the payment.
        :param payCurrency: The currency symbol for the payment.
        :param callbackUrl: The URL where payment information will be sent. Defaults to None.
        :param payAmount: The amount to be paid. Defaults to None.
        :param currency: The currency symbol for calculating the invoice amount. Defaults to None.
        :param email: The payer's email address for reporting purposes. Defaults to None.
        :param orderId: The unique order ID for reference in your system. Defaults to None.
        :param description: The order details or any additional information. Defaults to None.
        :param underPaidCover: The acceptable inaccuracy in payment. Defaults to None.
        :param feePaidByPayer: Whether the payer will cover the invoice commission. Defaults to None.
        :param lifeTime: The expiration time for the payment link in minutes. Defaults to None.
        :param network: The blockchain network on which the payment should be created. Defaults to None.
        :return: The payment information.
        """
        payment_data = {
            'merchant': self.merchant_api_key,
            'amount': amount,
            'payCurrency': payCurrency,
            'callbackUrl': callbackUrl,
            'payAmount': payAmount,
            'currency': currency,
            'email': email,
            'orderId': orderId,
            'description': description,
            'underPaidCover': underPaidCover,
            'feePaidByPayer': feePaidByPayer,
            'lifeTime': lifeTime,
            'network': network
        }
        try:
            return self.client.request('POST', 'merchants/request/whitelabel', json_data=payment_data)
        except Exception:
            raise Exception

    def create_static_address(
            self,
            currency: str,
            callbackUrl: str = None,
            network: str = None
    ):
        """
        Creates a static wallet address for receiving payments.

        :param currency: The currency symbol for which to create the static address.
        :param callbackUrl: The URL where payment information will be sent. Defaults to None.
        :param network: The blockchain network on which the static address should be created. Defaults to None.
        :return: The generated static address.
        """
        static_address_data = {
            'merchant': self.merchant_api_key,
            'currency': currency,
            'callbackUrl': callbackUrl,
            'network': network
        }
        try:
            return self.client.request('POST', 'merchants/request/staticaddress', json_data=static_address_data)
        except Exception:
            raise Exception

    def revoke_static_wallet(self, address: str):
        """
        Revokes a static wallet by disabling further transactions to the specified address.

        :param address: The address of the static wallet to revoke.
        :return: The result of the revocation process.
        """
        data = {
            'merchant': self.merchant_api_key,
            'address': address
        }
        try:
            return self.client.request('POST', 'merchants/revoke/staticaddress', json_data=data)
        except Exception:
            raise Exception

    def get_payment_history(
            self,
            orderBy: str = 'desc',
            sortBy: str = 'create_date',
            trackId: int = None,
            page: int = 1,
            size: int = 10,
            orderId: str = None,
            status: str = None,
            feePaidByPayer: float = None,
            type: str = None,
            network: str = None,
            payCurrency: str = None,
            currency: str = None,
            toAmount: float = None,
            fromAmount: float = None,
            toDate: str = None,
            fromDate: str = None,
            address: str = None,
            txID: str = None
    ):
        """
        Retrieves the payment history based on specified filters.

        :param orderBy: Display the list in ascending or descending order. Default: 'desc'.
        :param sortBy: Sort the list by a parameter. Default: 'create_date'.
        :param trackId: Filter payments by a specific invoice ID. Defaults to None.
        :param page: The page number to retrieve. Default: 1.
        :param size: Number of records per page. Default: 10.
        :param orderId: Filter payments by a unique order ID. Defaults to None.
        :param status: Filter payments by status. Defaults to None.
        :param feePaidByPayer: Filter payments by fee payment. Defaults to None.
        :param type: Filter payments by type. Defaults to None.
        :param network: Filter payments by blockchain network. Defaults to None.
        :param payCurrency: Filter payments by pay currency. Defaults to None.
        :param currency: Filter payments by currency. Defaults to None.
        :param toAmount: Filter payments with amounts less than or equal to this value. Defaults to None.
        :param fromAmount: Filter payments with amounts greater than or equal to this value. Defaults to None.
        :param toDate: The end of the date window to query for invoices in unix format. Defaults to None.
        :param fromDate: The start of the date window to query for invoices in unix format. Defaults to None.
        :param address: Filter payments by address. Defaults to None.
        :param txID: Filter payments by transaction hash. Defaults to None.
        :return: The payment history.
        """
        data = {
            'merchant': self.merchant_api_key,
            'orderBy': orderBy,
            'sortBy': sortBy,
            'trackId': trackId,
            'page': page,
            'size': size,
            'orderId': orderId,
            'status': status,
            'feePaidByPayer': feePaidByPayer,
            'type': type,
            'network': network,
            'payCurrency': payCurrency,
            'currency': currency,
            'toAmount': toAmount,
            'fromAmount': fromAmount,
            'toDate': toDate,
            'fromDate': fromDate,
            'address': address,
            'txID': txID
        }
        try:
            return self.client.request('POST', 'merchants/list', json_data=data)
        except Exception:
            raise Exception

    def get_accepted_coins(self):
        """
        Retrieves the list of cryptocurrencies accepted for payments through OxaPay.

        :return: The list of accepted coins.
        """
        data = {'merchant': self.merchant_api_key}
        try:
            return self.client.request('POST', 'merchants/allowedCoins', json_data=data)
        except Exception:
            raise Exception

    def get_prices(self):
        """
        Retrieves the current prices of all cryptocurrencies supported by OxaPay.

        :return: The current prices.
        """
        try:
            return self.client.request('POST', 'api/prices')
        except Exception:
            raise Exception

    def get_exchange_rate(self, from_currency: str, to_currency: str):
        """
        Retrieves the exchange rate between two currencies.

        :param from_currency: The currency to convert from.
        :param to_currency: The currency to convert to.
        :return: The exchange rate between the two currencies.
        """
        try:
            exchange_data = {
                'fromCurrency': from_currency,
                'toCurrency': to_currency
            }
            return self.client.request('POST', 'exchange/rate', json_data=exchange_data)
        except Exception:
            raise Exception

    def calculate_exchange(self, from_currency: str, to_currency: str, amount: float):
        """
        Calculates the amount of cryptocurrency you'll receive when exchanging from one type to another.

        :param from_currency: The currency code of the cryptocurrency you want to convert from.
        :param to_currency: The currency code of the cryptocurrency you want to convert to.
        :param amount: The amount you want to exchange.
        :return: The calculated exchange details.
        """
        try:
            exchange_data = {
                'fromCurrency': from_currency,
                'toCurrency': to_currency,
                'amount': amount
            }
            return self.client.request('POST', 'exchange/calculate', json_data=exchange_data)
        except Exception:
            raise Exception

    def get_exchange_pairs(self):
        """
        Retrieves a list of exchangeable cryptocurrencies along with their minimum conversion amounts.

        :return: The list of exchange pairs.
        """
        try:
            return self.client.request('POST', 'api/pairs')
        except Exception:
            raise Exception
