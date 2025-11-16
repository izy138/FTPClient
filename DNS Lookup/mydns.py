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
    """Class to build and parse DNS query and response messages
    
    here we create a class to build and parse the DNS query and response messages"""
    
    def __init__(self, domain):
        self.domain = domain
        self.transaction_id = random.randint(0, 65535) # random 16 bit transaction id for the query
    
    def build_query(self):
        """Build a DNS query packet"""
        # DNS header is the first 12 bytes of the DNS packet
        # Transaction id is 16 bits used to match responses to queries
        transaction_id = self.transaction_id 
        
        # Flags are 16 bits used to control the query and response
        flags = 0x0000
        
        # Questions count is 16 bits
        questions = 1
        
        # Answer RRs count is 16 bits
        answer_rrs = 0
        
        # Authority RRs count is 16 bits
        authority_rrs = 0
        
        # Additional RRs count is 16 bits
        additional_rrs = 0
        
        # pack the header into a 12 byte string using the struct module
        header = struct.pack('!HHHHHH', 
                           transaction_id, 
                           flags, 
                           questions, 
                           answer_rrs, 
                           authority_rrs, 
                           additional_rrs)
        
        # now build the question section
        # first encode the domain name in DNS format
        question = self._encode_domain_name(self.domain)
        
        # QTYPE is 16 bits used to specify the type of record
        qtype = 1 # 1 is the type of record that contains the IP address of the domain
        
        # QCLASS is 16 bits used to specify the class of the record
        qclass = 1 # 1 is the class of the record that contains the IN (Internet) class
        
        # pack the question section into a 4 byte string
        question += struct.pack('!HH', qtype, qclass)
        
        # combine the header and question section into a single packet
        return header + question
    

    def _encode_domain_name(self, domain):
        """Encode domain name into DNS format
        
        the format:
        - Each label separated by dots is prefixed by its length in bytes
        - The name ends with a zero-length label (null byte)
        
        example:
        "cs.fiu.edu" becomes:
        [2]cs[3]fiu[3]edu[0]
        where [n] is a single byte with value n and the 0 is the end of the domain name
        """
        encoded = b'' # initialize the encoded string as an empty byte string
        # split domain into labels (parts separated by dots)
        for label in domain.split('.'):
            length = len(label) # get the length of the label
            encoded += struct.pack('!B', length) # pack the length of the label into a single byte
            encoded += label.encode('ascii') # encode the label into a byte string
        encoded += b'\x00'  # end with null byte
        return encoded
    
    def parse_response(self, data):
        """Parse DNS response packet
        
        here we need to parse the header, question section, answer section, authority section, and additional section"""
        # parse header first 12 bytes
        header = data[:12]
        # unpack the 6 header fields with each field being 2 bytes each
        transaction_id, flags, questions, answer_rrs, authority_rrs, additional_rrs = \
            struct.unpack('!HHHHHH', header)
        
        # we skkip the question section
        offset = 12 # offset is the current position in the packet (12)
        offset = self._skip_question_section(data, offset, questions) # skip the question section
        
        # next parse the answer section
        answers = [] # initialize the answers list
        offset = self._parse_resource_records(data, offset, answer_rrs, answers) # parse the answer section, add the answer records to the list
        
        # next we parse the authority section
        authorities = [] # initialize the authorities list
        offset = self._parse_resource_records(data, offset, authority_rrs, authorities) # parse the authority section, add the authority records to the list
        
        # next parse the additional section
        additionals = [] # initialize the additionals list
        offset = self._parse_resource_records(data, offset, additional_rrs, additionals) # parse the additional section, add the additional records to the list
        
        # return the results in a dictionary
        return {
            'answers': answers, # list of answer records
            'authorities': authorities, # list of authority records
            'additionals': additionals, # list of additional records
            'answer_count': answer_rrs, # count of answer records
            'authority_count': authority_rrs, # count of authority records
            'additional_count': additional_rrs # count of additional records
        }
    
    def _skip_question_section(self, data, offset, count):
        """Skip the question section of the DNS response
        
        this section contains the question section of the DNS response, we skip the domain name and the QTYPE and QCLASS"""
        for _ in range(count): 
            # use the offset to skip the domain name
            offset = self._skip_domain_name(data, offset)
            # add 4 bytes to the offset to skip the QTYPE and QCLASS
            offset += 4
        return offset
    
    def _skip_domain_name(self, data, offset):
        """Skip domain name in the DNS packet
        
        this section contains the domain name of the DNS response, we skip the domain name and the QTYPE and QCLASS"""
        while True:
            length = data[offset] #read the length of the domain name
            if length == 0: # if the length is 0, we have reached the end of the domain name
                offset += 1 # increment the offset by 1
                break 
            elif (length & 0xC0) == 0xC0:  # compression pointer
                offset += 2 # increment the offset by 2
                break 
            else:
                offset += length + 1 # increment the offset by the length of the domain name plus 1
        return offset
    
    def _parse_domain_name(self, data, offset):
        """Parse a domain name from the DNS packet
        
        we parse the domain name from the DNS packet by reading the length of the domain name and then the domain name itself, if the length is 0, we have reached the end of the domain name, if the length is not 0, we have a compression pointer, we then remove the compression bits and set the offset to the new offset"""
        labels = [] # initialize the labels list
        jumped = False # jumped flag to check if we have jumped to a different offset
        original_offset = offset # initialize the original offset
        
        while True:
            length = data[offset] # read the length of the domain name
            
            if length == 0: # if the length is 0, we have reached the end of the domain name
                offset += 1 # we continue to increment the offset by 1
                break
            elif (length & 0xC0) == 0xC0:  # this is for the compression pointer
                if not jumped:
                    original_offset = offset + 2
                pointer = struct.unpack('!H', data[offset:offset+2])[0]
                pointer &= 0x3FFF  # remove the compression bits
                offset = pointer # set the offset to the new offset
                jumped = True # this means we have jumped to a different offset
            else:
                offset += 1
                labels.append(data[offset:offset+length].decode('ascii', errors='ignore')) # add the label to the labels list
                offset += length # increment the offset by the length of the label
        
        if jumped:
            return '.'.join(labels), original_offset
        else:
            return '.'.join(labels), offset
    
    def _parse_resource_records(self, data, offset, count, records):
        """Parse resource records section from the DNS packet
        
        this section contains the resource records for the domain name
        the name is a variable that contains the domain name, the type is 16 bits (2 bytes), the class is 16 bits (2 bytes), the ttl is 32 bits (4 bytes), and the rdlength is 16 bits (2 bytes), and then the rdata is the actual data for the record in the next 2 bytes"""
        for _ in range(count):
            # we parse the domain name again and set the offset to the new offset
            name, offset = self._parse_domain_name(data, offset)
            
            # we parse the TYPE, CLASS, TTL, and RDLENGTH by unpacking the 4 bytes into 4 variables
            rr_type, rr_class, ttl, rdlength = struct.unpack('!HHIH', data[offset:offset+10])
            offset += 10 # increment the offset by 10 because we have parsed the 4 bytes
            
            # next we parse the RDATA
            rdata_start = offset # set the start of the rdata to the current offset
            rdata_end = offset + rdlength # set the end of the rdata to the current offset plus the rdlength
            
            record = { # create a dictionary to store the records
                'name': name,
                'type': rr_type,
                'class': rr_class,
                'ttl': ttl,
                'rdlength': rdlength
            }
            
            # then we parse the rdata based on the record type
            if rr_type == 1:  # A record
                if rdlength == 4: # if the rdlength is 4, we have an A record
                    ip = socket.inet_ntoa(data[rdata_start:rdata_end]) # convert the 4 bytes into an IP address
                    record['ip'] = ip # add the IP address to the record list
            elif rr_type == 2:  # this is for the NS record
                ns_name, _ = self._parse_domain_name(data, rdata_start) # parse the domain name and set the offset to the new offset
                record['nameserver'] = ns_name # add the domain name to the record list
            
            offset = rdata_end # set the offset to the end of the rdata and update the offset
            records.append(record) # add the record to the records list and update the offset
        
        return offset # return the offset, this is the new offset after parsing the resource records


def query_dns_server(domain, dns_server_ip, timeout=5):
    """Send a DNS query to a server and return the response
    
    first we create a UDP socket and send the query to the DNS server, we build the dns query packet and send it to the DNS server on port 53, we then receive the response from the DNS server and parse it, and then we return the response"""
    try:
        # create UDP socket and set the timeout
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # cCreate DNS query
        query = DNSQuery(domain)
        packet = query.build_query()
        
        # this sends the query to the DNS server
        sock.sendto(packet, (dns_server_ip, 53))
        
        # receive response from the DNS server
        data, _ = sock.recvfrom(4096)
        
        # then we parse the response
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
    print("Reply received. Overview:")
    print(f"{response['answer_count']} Answers.")
    print(f"{response['authority_count']} Intermediate Name Servers.")
    print(f"{response['additional_count']} Additional Information Records.")
    
    # display answers section
    print("\nAnswers section:")
    if response['answer_count'] == 0:
        print()
    else:
        for record in response['answers']:
            if record['type'] == 1:  # A record
                print(f"Name: {record['name']} IP: {record['ip']}")
    
    # display authority section
    print("\nAuthority Section:")
    for record in response['authorities']:
        if record['type'] == 2:  # NS record
            print(f"Name: {record['name']} Name Server: {record['nameserver']}")
    
    # display additional section
    print("\nAdditional Information Section:")
    for record in response['additionals']:
        if record['type'] == 1:  # A record
            print(f"Name: {record['name']} IP: {record['ip']}")
        elif record['type'] == 2:  # NS record
            print(f"Name: {record['name']}")


def get_next_server(response):
    """Extract the next DNS server IP to query
    
    we check if we have answers with A records. if we do, we return none.
    if not, it look for NS records in the authority section, and if found its domain name is added to the list.
    then it looks for IP addresses in the additional section we add the domain name to the list, we then find the IP addresses in the additional section."""

    # check the answer section for A records
    for record in response['answers']:
        if record['type'] == 1:  # A record found
            return None
    
    # next look for NS records in the authority section
    ns_servers = []
    for record in response['authorities']:
        if record['type'] == 2:  # NS record
            ns_servers.append(record['nameserver'])
    
    # find IP addresses in additional section for the NS servers
    for ns in ns_servers:
        for record in response['additionals']:
            if record['type'] == 1 and record['name'] == ns:  # A record
                return record['ip']
    
    # if no match found in additional section, try any A record
    for record in response['additionals']:
        if record['type'] == 1:  # A record
            return record['ip']
    
    return None


def iterative_dns_lookup(domain, root_dns_ip):
    """Perform iterative DNS lookup
    
    first the root DNS server is queried, if a response is received, it displays the response.
    if not, we get the next DNS server to query from the response, we then query the next DNS server, and so on until we run out of servers."""
    current_server = root_dns_ip # set the current server to the root DNS server
    
    while current_server: 
        print("-" * 64)
        print(f"DNS server to query: {current_server}")
        
        # query the current DNS server
        response = query_dns_server(domain, current_server)
        
        #this checks if the query failed
        if response is None:
            print("Failed to get response from DNS server")
            return False
        
        # display the response 
        display_response(response)
        
        # then check if we have an answer 
        has_answer = False
        for record in response['answers']:
            if record['type'] == 1:  # A record found
                has_answer = True
                break
        
        if has_answer:
            # we ip address found
            return True
        
        # now it gets the next server to query
        next_server = get_next_server(response)
        
        if next_server is None:
            print("\nError: Could not find next DNS server to query")
            return False
        
        current_server = next_server
    
    return False


def main():
    """Main function"""
    if len(sys.argv) != 3:
        print("Use: python mydns.py domain-name root-dns-ip")
        print("Ex: python mydns.py cs.fiu.edu 202.12.27.33")
        sys.exit(1)
    
    domain = sys.argv[1]
    root_dns_ip = sys.argv[2]
    
    # DNS lookup
    iterative_dns_lookup(domain, root_dns_ip)


if __name__ == "__main__":
    main() 