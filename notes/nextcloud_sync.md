With `nextcloud-docker` running (with docker-compose), find the local IP address in powershell with `ipconfig` (under "Wireless LAN adapter Wi-Fi -> IPv4 address).

Set in the WSL Joplin instance:

```sh
joplin config sync.5.path http://192.168.0.107:48916/remote.php/webdav/Joplin
```

Also change in the nextcloud-docker `config.php` file (under 'trusted_domains'), and docker-compose restart if necessary.

It's a good idea to assign the local device to a static IP (DHCP reservation) --- see, for example, <https://www.pcmag.com/how-to/how-to-set-up-a-static-ip-address>