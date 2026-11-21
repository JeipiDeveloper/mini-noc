FROM nginx:1.27-alpine

# iproute2 fornece o `tc`, usado no cenário de caos de latência.
# curl é útil para diagnóstico dentro do container durante a triagem.
RUN apk add --no-cache iproute2 curl

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY html/ /usr/share/nginx/html/

EXPOSE 80
