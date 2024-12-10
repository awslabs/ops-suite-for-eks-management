#!/bin/bash

ARCH=""
case $(uname -m) in
    x86_64) ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
esac

PLATFORM=$(uname -s)_$ARCH

KUBECTL_DOWNLOAD_URL="https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/$ARCH/kubectl"
KUBECTL_CHECKSUM_URL="https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/$ARCH/kubectl.sha256"

EKSCTL_DOWNLOAD_URL="https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_$PLATFORM.tar.gz"
EKSCTL_CHECKSUM_URL="https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_checksums.txt"

function install_kubectl(){
  echo 'Installing kubectl..'
  curl -LO "$KUBECTL_DOWNLOAD_URL"
  curl -LO "$KUBECTL_CHECKSUM_URL"

  echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check

  chmod +x ./kubectl
  mkdir -p $HOME/bin && cp ./kubectl $HOME/bin/kubectl && export PATH=$HOME/bin:$PATH
  echo 'export PATH=$HOME/bin:$PATH' >> ~/.bashrc
}

function install_eksctl(){
  echo 'Installing eksctl..'
  curl -sLO "$EKSCTL_DOWNLOAD_URL"
  # (Optional) Verify checksum
  curl -sL "$EKSCTL_CHECKSUM_URL"  | grep $PLATFORM | sha256sum --check

  tar -xzf eksctl_$PLATFORM.tar.gz -C /tmp && rm eksctl_$PLATFORM.tar.gz
  sudo mv /tmp/eksctl /usr/local/bin

}

function install_kubent() {
  echo 'Installing kubent..'
  export TERM=linux
  sh -c "$(curl -sSL $KUBENT_DOWNLOAD_URL)"  > /dev/null 2>&1
}

install_kubectl

kubectl version --client > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]] ;
then
    echo "Failed to install kubectl"
    exit 1
fi

install_eksctl

eksctl version > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]] ;
then
    echo "Failed to install eksctl"
    exit 1
fi
