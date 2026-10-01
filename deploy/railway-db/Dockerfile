FROM ghcr.io/railwayapp-templates/postgres-ssl:17
COPY --chmod=755 deploy/railway-db/start.sh /usr/local/bin/searchroom-start.sh
COPY --chmod=755 deploy/railway-db/init-app.sh /docker-entrypoint-initdb.d/zz-searchroom.sh
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/searchroom-start.sh"]
CMD ["postgres", "-p", "5432", "-c", "listen_addresses=*", "-c", "ssl=on", "-c", "ssl_cert_file=/tmp/searchroom-tls/server.crt", "-c", "ssl_key_file=/tmp/searchroom-tls/server.key"]
