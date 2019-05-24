#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
"""
About: On the Fly NC decoder
"""

import argparse
import copy
import kodo
import socket
import struct
import time

import common
import log
import rawsock_helpers as rsh
from common import (BUFFER_SIZE, FIELD, IO_SLEEP, MD_TYPE_TCP_IN_UDP,
                    MD_TYPE_UDP, META_DATA_LEN, MTU, SYMBOL_SIZE, SYMBOLS)

log.conf_logger("error")
logger = log.logger


def run_decoder(ifce):
    """Main IO loop"""

    rx_tx_buf = bytearray(BUFFER_SIZE)
    generation = 0
    udp_cnt = 0

    try:
        logger.info("Create a raw packet socket\n")
        # Create a raw socket to recv and send packets, the protocol number 3
        # means receive all types of Ethernet frames.
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                             socket.htons(3))
    except socket.error as error:
        raise error

    logger.info("Bind the socket to the interface: {}".format(ifce))
    sock.bind((ifce, 0))

    logger.info("Init kodo decoder...\n")
    # Create an encoder factory that are used to build the actual encoders
    decoder_factory = kodo.RLNCDecoderFactory(FIELD, SYMBOLS, SYMBOL_SIZE)
    decoder = decoder_factory.build()
    # Decoder buffer
    decode_buf = bytearray(decoder.block_size())
    decoder.set_mutable_symbols(decode_buf)
    not_decoded_indces = list(range(decoder.symbols()))

    logger.info("Entering IO loop.")

    while True:
        time.sleep(IO_SLEEP)
        ret = rsh.recv_ipv4(sock, rx_tx_buf, MTU)
        if not ret:
            logger.debug("Recv a non-IPv4 frame, frame is ignored.")
            continue
        frame_len, ip_hd_offset, ip_hd_len, proto = ret

        if proto == rsh.IP_PROTO_UDP:
            udp_cnt += 1
            logger.info(
                "Recv a UDP segment, total received UDP segments: %d "
                "frame len: %d",
                udp_cnt, frame_len)
        else:
            logger.debug("Recv a non-UDP segment. Ignore it.")
            continue

        # Only handle UDP segments
        udp_hd_offset, _, udp_pl_offset, udp_pl_len = rsh.parse_udp(
            rx_tx_buf, ip_hd_offset, ip_hd_len)
        logger.debug("UDP HD offset:%d, pl_offset:%d, pl_len:%d", udp_hd_offset,
                     udp_pl_offset, udp_pl_len)

        _type, cur_gen, md_pl_len = common.pull_metadata(
            rx_tx_buf, udp_pl_offset)
        logger.debug(
            "Generation number in payload:%d, current decode generation:%d, md_pl_len:%d",
            cur_gen, generation, md_pl_len)

        if cur_gen > generation:
            logger.debug("Cleanup decoder for new generation")
            decoder = decoder_factory.build()
            decode_buf = bytearray(decoder.block_size())
            decoder.set_mutable_symbols(decode_buf)
            not_decoded_indces = list(range(decoder.symbols()))
            generation = cur_gen

        coded_symbol = copy.deepcopy(
            rx_tx_buf[udp_pl_offset+META_DATA_LEN:frame_len])
        decoder.read_payload(coded_symbol)
        logger.debug("Decode rank: %d/%d, coded symbol len:%d",
                     decoder.rank(), decoder.symbols(), len(coded_symbol))

        # Loop over un-decoded symbols
        for i in not_decoded_indces:
            if decoder.is_symbol_uncoded(i):
                del not_decoded_indces[not_decoded_indces.index(i)]
                logger.debug(
                    "Decoder symbol:%d, not_decoded_symbols_indces:%s",
                    i, ",".join(map(str, not_decoded_indces))
                )

                if _type == MD_TYPE_UDP:
                    rx_tx_buf[
                        udp_pl_offset:udp_pl_offset+md_pl_len] = decode_buf[
                            i * SYMBOL_SIZE:i*SYMBOL_SIZE+md_pl_len]
                    udp_total_len = rsh.UDP_HDL + md_pl_len
                    ip_total_len = udp_total_len + ip_hd_len
                    frame_len = ip_total_len + rsh.ETH_HDL
                    logger.debug("[Decoder TX] UDP total len:%d, ip_total_len:%d",
                                 udp_total_len, ip_total_len)
                    rsh.update_ip_udp_len(rx_tx_buf, ip_hd_offset, udp_hd_offset,
                                          ip_total_len, udp_total_len)
                    struct.pack_into(">H", rx_tx_buf, udp_hd_offset+6, 0)
                    rsh.update_cksum_ipv4(rx_tx_buf, ip_hd_offset, ip_hd_len)
                    sock.send(rx_tx_buf[:frame_len])

                elif _type == MD_TYPE_TCP_IN_UDP:
                    continue
                    # Bad codes... Should be corrected by Zuo
                    tcp_seg = decode_buf[
                        i * SYMBOL_SIZE + rsh.UDP_HDL:(i+1)*SYMBOL_SIZE+rsh.UDP_HDL]
                    st = ip_hd_offset + ip_hd_len
                    ed = st + tcp_seg
                    rx_tx_buf[st:ed] = tcp_seg[:]
                    ip_total_len = ip_hd_len + len(tcp_seg)
                    struct.pack_into(
                        ">H", rx_tx_buf, ip_hd_offset+2, ip_total_len)
                    rsh.update_cksum_ipv4(rx_tx_buf, ip_hd_offset, ip_hd_len)
                    sock.send(rx_tx_buf[:ip_total_len+rsh.ETH_HDL])


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("ifce",
                        help="The name of interface for recv and send frames",
                        type=str)
    args = parser.parse_args()

    ifce = args.ifce

    run_decoder(ifce)