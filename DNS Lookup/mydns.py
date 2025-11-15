#!/usr/bin/env python3
"""
DNS Lookup Client - CNT 4713 Project 2
Performs iterative DNS queries using UDP socket programming
"""

import socket
import sys
import struct
import random


class DNSQuery:
    """Class to build and parse DNS query and response messages"""
    
    def __init__(self, domain):
        self.domain = domain
        self.transaction_id = random.randint(0, 65535)
    
    def build_query(self):
        """Build a DNS query packet"""
        # DNS Header
        # Transaction ID: 16 bits
        transaction_id = self.transaction_id
        
        # Flags: 16 bits
        # QR=0 (query), OPCODE=0 (standard query), AA=0, TC=0, RD=0 (no recursion)
        # RA=0, Z=0, RCODE=0
        flags = 0x0000
        
        # Questions: 16 bits
        questions = 1
        
        # Answer RRs: 16 bits
        answer_rrs = 0
        
        # Authority RRs: 16 bits
        authority_rrs = 0
        
        # Additional RRs: 16 bits
        additional_rrs = 0
        
        # Pack the header
        header = struct.pack('!HHHHHH', 
                           transaction_id, 
                           flags, 
                           questions, 
                           answer_rrs, 
                           authority_rrs, 
                           additional_rrs)
        
        # Build the question section
        question = self._encode_domain_name(self.domain)
        
        # QTYPE: A record (1)
        qtype = 1
        
        # QCLASS: IN (1)
        qclass = 1
        
        question += struct.pack('!HH', qtype, qclass)
        
        return header + question
    
    def _encode_domain_name(self, domain):
        """Encode domain name in DNS format"""
        encoded = b''
        for label in domain.split('.'):
            length = len(label)
            encoded += struct.pack('!B', length)
            encoded += label.encode('ascii')
        encoded += b'\x00'  # End with null byte
        return encoded
    
    def parse_response(self, data):
        """Parse DNS response packet"""
        # Parse header
        header = data[:12]
        transaction_id, flags, questions, answer_rrs, authority_rrs, additional_rrs = \
            struct.unpack('!HHHHHH', header)
        
        # Skip the question section
        offset = 12
        offset = self._skip_question_section(data, offset, questions)
        
        # Parse answer section
        answers = []
        offset = self._parse_resource_records(data, offset, answer_rrs, answers)
        
        # Parse authority section
        authorities = []
        offset = self._parse_resource_records(data, offset, authority_rrs, authorities)
        
        # Parse additional section
        additionals = []
        offset = self._parse_resource_records(data, offset, additional_rrs, additionals)
        
        return {
            'answers': answers,
            'authorities': authorities,
            'additionals': additionals,
            'answer_count': answer_rrs,
            'authority_count': authority_rrs,
            'additional_count': additional_rrs
        }
    
    def _skip_question_section(self, data, offset, count):
        """Skip the question section of the DNS response"""
        for _ in range(count):
            # Skip the domain name
            offset = self._skip_domain_name(data, offset)
            # Skip QTYPE and QCLASS (4 bytes)
            offset += 4
        return offset
    
    def _skip_domain_name(self, data, offset):
        """Skip a domain name in the DNS packet"""
        while True:
            length = data[offset]
            if length == 0:
                offset += 1
                break
            elif (length & 0xC0) == 0xC0:  # Compression pointer
                offset += 2
                break
            else:
                offset += length + 1
        return offset
    
    def _parse_domain_name(self, data, offset):
        """Parse a domain name from the DNS packet"""
        labels = []
        jumped = False
        original_offset = offset
        
        while True:
            length = data[offset]
            
            if length == 0:
                offset += 1
                break
            elif (length & 0xC0) == 0xC0:  # Compression pointer
                if not jumped:
                    original_offset = offset + 2
                pointer = struct.unpack('!H', data[offset:offset+2])[0]
                pointer &= 0x3FFF  # Remove the compression bits
                offset = pointer
                jumped = True
            else:
                offset += 1
                labels.append(data[offset:offset+length].decode('ascii', errors='ignore'))
                offset += length
        
        if jumped:
            return '.'.join(labels), original_offset
        else:
            return '.'.join(labels), offset
    
    def _parse_resource_records(self, data, offset, count, records):
        """Parse resource records from the DNS packet"""
        for _ in range(count):
            # Parse domain name
            name, offset = self._parse_domain_name(data, offset)
            
            # Parse TYPE, CLASS, TTL, and RDLENGTH
            rr_type, rr_class, ttl, rdlength = struct.unpack('!HHIH', data[offset:offset+10])
            offset += 10
            
            # Parse RDATA
            rdata_start = offset
            rdata_end = offset + rdlength
            
            record = {
                'name': name,
                'type': rr_type,
                'class': rr_class,
                'ttl': ttl,
                'rdlength': rdlength
            }
            
            # Parse based on record type
            if rr_type == 1:  # A record
                if rdlength == 4:
                    ip = socket.inet_ntoa(data[rdata_start:rdata_end])
                    record['ip'] = ip
            elif rr_type == 2:  # NS record
                ns_name, _ = self._parse_domain_name(data, rdata_start)
                record['nameserver'] = ns_name
            
            offset = rdata_end
            records.append(record)
        
        return offset


def query_dns_server(domain, dns_server_ip, timeout=5):
    """Send a DNS query to a server and return the response"""
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # Create DNS query
        query = DNSQuery(domain)
        packet = query.build_query()
        
        # Send query to DNS server
        sock.sendto(packet, (dns_server_ip, 53))
        
        # Receive response
        data, _ = sock.recvfrom(4096)
        
        # Parse response
        response = query.parse_response(data)
        
        sock.close()
        return response
    
    except socket.timeout:
        print(f"Error: Timeout while querying {dns_server_ip}")
        return None
    except Exception as e:
        print(f"Error querying DNS server: {e}")
        return None


def display_response(response):
    """Display the DNS response content"""
    print("Reply received. Content overview:")
    print(f"{response['answer_count']} Answers.")
    print(f"{response['authority_count']} Intermediate Name Servers.")
    print(f"{response['additional_count']} Additional Information Records.")
    
    # Display answers
    print("\nAnswers section:")
    if response['answer_count'] == 0:
        print()
    else:
        for record in response['answers']:
            if record['type'] == 1:  # A record
                print(f"Name : {record['name']} IP: {record['ip']}")
    
    # Display authority section
    print("\nAuthority Section:")
    for record in response['authorities']:
        if record['type'] == 2:  # NS record
            print(f"Name : {record['name']} Name Server: {record['nameserver']}")
    
    # Display additional section
    print("\nAdditional Information Section:")
    for record in response['additionals']:
        if record['type'] == 1:  # A record
            print(f"Name : {record['name']} IP : {record['ip']}")
        elif record['type'] == 2:  # NS record
            print(f"Name : {record['name']}")


def get_next_server(response):
    """Extract the next DNS server IP to query"""
    # First check if we have answers with A records
    for record in response['answers']:
        if record['type'] == 1:  # A record found, we're done
            return None
    
    # Look for NS records in authority section
    ns_servers = []
    for record in response['authorities']:
        if record['type'] == 2:  # NS record
            ns_servers.append(record['nameserver'])
    
    # Find IP addresses in additional section for the NS servers
    for ns in ns_servers:
        for record in response['additionals']:
            if record['type'] == 1 and record['name'] == ns:  # A record
                return record['ip']
    
    # If no match found in additional section, try any A record
    for record in response['additionals']:
        if record['type'] == 1:  # A record
            return record['ip']
    
    return None


def iterative_dns_lookup(domain, root_dns_ip):
    """Perform iterative DNS lookup"""
    current_server = root_dns_ip
    
    while current_server:
        print("-" * 64)
        print(f"DNS server to query: {current_server}")
        
        # Query the current DNS server
        response = query_dns_server(domain, current_server)
        
        if response is None:
            print("Failed to get response from DNS server")
            return False
        
        # Display the response
        display_response(response)
        
        # Check if we have an answer
        has_answer = False
        for record in response['answers']:
            if record['type'] == 1:  # A record
                has_answer = True
                break
        
        if has_answer:
            # We found the IP address, stop
            return True
        
        # Get the next server to query
        next_server = get_next_server(response)
        
        if next_server is None:
            print("\nError: Could not find next DNS server to query")
            return False
        
        current_server = next_server
    
    return False


def main():
    """Main function"""
    if len(sys.argv) != 3:
        print("Usage: python mydns.py domain-name root-dns-ip")
        print("Example: python mydns.py cs.fiu.edu 202.12.27.33")
        sys.exit(1)
    
    domain = sys.argv[1]
    root_dns_ip = sys.argv[2]
    
    # Perform iterative DNS lookup
    iterative_dns_lookup(domain, root_dns_ip)


if __name__ == "__main__":
    main()