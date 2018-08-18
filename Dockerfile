FROM python:alpine3.8

ENV PYTHONUNBUFFERED=1

RUN apk --update add make vim emacs

RUN apk --update add gcc musl-dev gmp-dev

# for .[eth] extras
RUN apk --update add libffi-dev openssl-dev
RUN apk --update add nodejs npm git cmake g++
RUN npm install -g ganache-cli
RUN git clone --recursive https://github.com/ethereum/solidity.git
WORKDIR solidity
RUN git checkout v0.4.24 # Old version necessary to work???
RUN git submodule update --init --recursive
RUN ./scripts/install_deps.sh
RUN mkdir build/
WORKDIR build
RUN cmake ..
RUN make install

RUN mkdir -p /usr/src/HoneyBadgerMPC
WORKDIR /usr/src/HoneyBadgerMPC

RUN pip install --upgrade pip

COPY . /usr/src/HoneyBadgerMPC

RUN pip install --no-cache-dir -e .[dev] .[eth]
