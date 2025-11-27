DNS Lookup
Isabella Correa 6043518
Justin Cardena 6399432
Martin Valencia 6443987

Language: Python

Video: https://www.youtube.com/watch?v=Vm1PpRet5r0

This program implements an iterative DNS lookup using UDP socket programming. The client constructs DNS query packets sends them to DNS servers starting from a root server, and parses the binary responses to extract records. 
We are looking for the address for cs.fiu.edu server using:
> python3 mydns.py cs.fiu.edu 202.12.27.33

It performs iterative resolution by following the DNS hierarchy through root servers, TLD servers, and authoritative servers until an A record is found. 
The program handles DNS name compression, extracts NS and A records from Authority and Additional sections, and automatically selects the next intermediate DNS server to query. 
Finally, it reaches an answer and that IP address is verified as the correct IP address for the requested domain using 
> nslookup cs.fiu.edu 8.8.8.8 

