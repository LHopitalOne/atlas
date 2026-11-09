FROM node:22-alpine
WORKDIR /srv
COPY package*.json ./
RUN npm install
COPY . .
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "41830"]
