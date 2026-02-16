import { useState, useEffect } from 'react';
import { RAZORPAY_KEY_ID } from '../config';
import { verifyPayment } from '../services/api';

const RazorpayCheckout = ({ order, onSuccess, onFailure }) => {
    useEffect(() => {
        if (!order) return;

        // Load Razorpay script
        const script = document.createElement('script');
        script.src = 'https://checkout.razorpay.com/v1/checkout.js';
        script.async = true;
        script.onload = () => {
            const options = {
                key: RAZORPAY_KEY_ID,
                amount: order.amount,
                currency: order.currency,
                name: order.name,
                description: order.description,
                order_id: order.order_id,
                handler: async function (response) {
                    try {
                        await verifyPayment({
                            payment_id: response.razorpay_payment_id,
                            order_id: response.razorpay_order_id,
                            signature: response.razorpay_signature,
                        });
                        alert('Payment Verified Successfully! Credits added.');
                        if (onSuccess) onSuccess();
                    } catch (error) {
                        alert('Verification Failed: ' + (error.response?.data?.detail || error.message));
                        if (onFailure) onFailure(error);
                    }
                },
                theme: {
                    color: '#818cf8',
                },
                modal: {
                    ondismiss: function () {
                        if (onFailure) onFailure(new Error('Payment cancelled'));
                    }
                }
            };

            const rzp = new window.Razorpay(options);
            rzp.on('payment.failed', function (response) {
                alert('Payment Failed: ' + response.error.description);
                if (onFailure) onFailure(new Error(response.error.description));
            });
            rzp.open();
        };
        document.body.appendChild(script);

        return () => {
            // Cleanup script if component unmounts
            if (document.body.contains(script)) {
                document.body.removeChild(script);
            }
        };
    }, [order, onSuccess, onFailure]);

    return null;
};

export default RazorpayCheckout;
