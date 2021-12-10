With `nextcloud-docker` running (with docker-compose), find the local IP address in powershell with `ipconfig` (under "Wireless LAN adapter Wi-Fi -> IPv4 address).

Set in the WSL Joplin instance:

```sh
joplin config sync.5.path http://192.168.0.107:8080/remote.php/webdav/Joplin
```

Also change in the nextcloud-docker `config.php` file (under 'trusted_domains'), and docker-compose restart if necessary.