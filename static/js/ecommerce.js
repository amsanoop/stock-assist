function trackSubscriptionView(subscriptionPlans) {
    /**
     * Tracks the view of subscription plans.
     * 
     * @param {Array} subscriptionPlans - The list of subscription plans.
     */
    if (typeof gtag !== 'function') return;

    const items = subscriptionPlans.map((plan, index) => ({
        item_id: plan.id,
        item_name: plan.name,
        price: plan.price,
        item_category: 'Subscription',
        index: index,
        quantity: 1
    }));

    gtag('event', 'view_item_list', {
        item_list_id: 'subscription_plans',
        item_list_name: 'Subscription Plans',
        items: items
    });
}

function trackSubscriptionSelect(plan) {
    /**
     * Tracks the selection of a subscription plan.
     * 
     * @param {Object} plan - The selected subscription plan.
     */
    if (typeof gtag !== 'function') return;

    gtag('event', 'select_item', {
        item_list_id: 'subscription_plans',
        item_list_name: 'Subscription Plans',
        items: [{
            item_id: plan.id,
            item_name: plan.name,
            price: plan.price,
            item_category: 'Subscription',
            quantity: 1
        }]
    });
}

function trackSubscriptionCheckout(plan) {
    /**
     * Tracks the checkout of a subscription plan.
     * 
     * @param {Object} plan - The subscription plan being checked out.
     */
    if (typeof gtag !== 'function') return;

    gtag('event', 'begin_checkout', {
        currency: 'USD',
        value: plan.price,
        items: [{
            item_id: plan.id,
            item_name: plan.name,
            price: plan.price,
            item_category: 'Subscription',
            quantity: 1
        }]
    });
}

function trackSubscriptionPurchase(plan, transactionId) {
    /**
     * Tracks the purchase of a subscription plan.
     * 
     * @param {Object} plan - The purchased subscription plan.
     * @param {string} transactionId - The transaction ID for the purchase.
     */
    if (typeof gtag !== 'function') return;

    gtag('event', 'purchase', {
        transaction_id: transactionId,
        value: plan.price,
        currency: 'USD',
        tax: 0,
        shipping: 0,
        items: [{
            item_id: plan.id,
            item_name: plan.name,
            price: plan.price,
            item_category: 'Subscription',
            quantity: 1
        }]
    });
}

function trackRedemptionKey(keyType, subscriptionName, durationDays) {
    /**
     * Tracks the usage of a redemption key.
     * 
     * @param {string} keyType - The type of the key being redeemed.
     * @param {string} subscriptionName - The name of the subscription.
     * @param {number} durationDays - The duration of the subscription in days.
     */
    if (typeof gtag !== 'function') return;

    gtag('event', 'redeem_key', {
        key_type: keyType,
        subscription_name: subscriptionName,
        duration_days: durationDays
    });
}

document.addEventListener('DOMContentLoaded', function() {
    if (window.location.pathname.includes('/pricing')) {
        const subscriptionPlans = [];

        const planElements = document.querySelectorAll('.subscription-plan');
        planElements.forEach((element, index) => {
            const planId = element.dataset.planId;
            const planName = element.dataset.planName;
            const planPrice = parseFloat(element.dataset.planPrice || '0');

            subscriptionPlans.push({
                id: planId,
                name: planName,
                price: planPrice,
                index: index
            });

            element.addEventListener('click', function() {
                trackSubscriptionSelect({
                    id: planId,
                    name: planName,
                    price: planPrice
                });
            });
        });

        if (subscriptionPlans.length > 0) {
            trackSubscriptionView(subscriptionPlans);
        }
    }

    if (window.location.pathname.includes('/redeem')) {
        const redeemForm = document.querySelector('form');
        if (redeemForm) {
            redeemForm.addEventListener('submit', function() {
                const keyInput = document.querySelector('input[name="key"]');
                if (keyInput && keyInput.value) {
                    gtag('event', 'redeem_key_attempt', {
                        key_length: keyInput.value.length
                    });
                }
            });
        }
    }
});