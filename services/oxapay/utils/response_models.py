class OrderStatus:
    def __init__(
            self,
            result: int,
            message: str = None,
            trackId: str =None,
            expiredAt: int = None,
            payLink: str = None
    ):
        self.result = result
        self.message = message
        self.trackId = trackId
        self.expiredAt = expiredAt
        self.payLink = payLink

class PaymentStatus:
    def __init__(
            self,
            result: int,
            message: str = None,
            trackId: str = None,
            createdAt: str = None,
            address: str = None,
            amount: str = None,
            currency: str = None,
            payAmount: str = None,
            payCurrency: str = None,
            receivedAmount: str = None,
            rate: str = None,
            network: str = None,
            feePaidByPayer: float = None,
            underPaidCover: float = None,
            status: str = None,
            type: str = None,
            txID: str = None,
            date: str = None,
            expiredAt: str = None,
            payDate: str = None,
            email: str = None,
            orderId: str = None,
            description: str = None
    ):
        self.result = result
        self.message = message
        self.trackId = trackId
        self.createdAt = createdAt
        self.status = status
        self.address = address
        self.amount = amount
        self.currency = currency
        self.payAmount = payAmount
        self.payCurrency = payCurrency
        self.receivedAmount = receivedAmount
        self.rate = rate
        self.network = network
        self.feePaidByPayer = feePaidByPayer
        self.underPaidCover = underPaidCover
        self.type = type
        self.txID = txID
        self.date = date
        self.expiredAt = expiredAt
        self.payDate = payDate
        self.email = email
        self.orderId = orderId
        self.description = description
