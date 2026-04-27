package com.modstore.event;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class EventContractsTest {

    @Test
    void canonicalNameMapsLegacyAndPassthrough() {
        assertEquals("payment.paid", EventContracts.canonicalName("payment.order_paid"));
        assertEquals("refund.approved", EventContracts.canonicalName("refund.approved"));
        assertEquals("", EventContracts.canonicalName(null));
    }

    @Test
    void versionIsOneForV1Events() {
        assertEquals(1, EventContracts.version("payment.paid"));
        assertEquals(1, EventContracts.version("unknown.noop"));
    }
}
