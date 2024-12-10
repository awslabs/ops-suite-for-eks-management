#!/bin/bash

lib_directory=$1

ARCH=""
case $(uname -m) in
    x86_64) ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
esac

PLATFORM=$(uname -s)_$ARCH

AWS_CLI_DOWNLOAD_URL="https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip"
KUBECTL_DOWNLOAD_URL="https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/$ARCH/kubectl"
KUBECTL_CHECKSUM_URL="https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/$ARCH/kubectl.sha256"

EKSCTL_DOWNLOAD_URL="https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_$PLATFORM.tar.gz"
EKSCTL_CHECKSUM_URL="https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_checksums.txt"

function install_python() {
  sudo yum -y install python3
  sudo yum -y install python3-pip
}

function install_pip() {
  sudo yum -y install python3-pip
}

function update_aws_cli(){
  sudo yum remove awscli -y
  rm -f -r aws 2>/dev/null && rm awscliv2.zip 2>/dev/null
  curl "$AWS_CLI_DOWNLOAD_URL" -o "awscliv2.zip"
  unzip awscliv2.zip
  sudo ./aws/install --update
  ## Bash caches the path of the older aws cli. Update the bash cache
  hash aws
}

function build_lib_wheel() {
  echo "Installing wheel package"
  pip3 install wheel

  echo "Building scripts library"
  resp=$(cd "$lib_directory" || exit 1 ;  mkdir -p  .tmp || exit 1; pip3 wheel --no-deps -w dist .;)
  error_code=${?}
  if [[ $error_code -ne 0 ]]; then
    echo "Failed to install scripts library..$resp"
    exit 1
  fi
}

function install_lib_wheel() {
  echo "Uninstalling scripts library"
  pip3 uninstall eks_workflow --yes

  echo "Installing scripts library.."
  resp=$(pip3 install -f "$lib_directory"/dist eks_workflow)
  error_code=${?}
  if [[ $error_code -ne 0 ]]; then
    echo "Failed to install scripts library..$resp"
    exit 1
  fi
}

function install_kubectl(){
  curl -LO "$KUBECTL_DOWNLOAD_URL"
  curl -LO "$KUBECTL_CHECKSUM_URL"

  echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check

  chmod +x ./kubectl
  mkdir -p $HOME/bin && cp ./kubectl $HOME/bin/kubectl && export PATH=$HOME/bin:$PATH
  echo 'export PATH=$HOME/bin:$PATH' >> ~/.bashrc
}

function install_eksctl(){
  curl -sLO "$EKSCTL_DOWNLOAD_URL"
  # (Optional) Verify checksum
  curl -sL "$EKSCTL_CHECKSUM_URL"  | grep $PLATFORM | sha256sum --check

  tar -xzf eksctl_$PLATFORM.tar.gz -C /tmp && rm eksctl_$PLATFORM.tar.gz
  sudo mv /tmp/eksctl /usr/local/bin

}

## Python Installation
python3 --version > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]]; then
  echo 'python3 not present. Installing..'
  install_python
fi

## Verify if the softwares are installed
python3 --version > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]]; then
    echo "Failed to install python"
    exit 1
fi

## Pip Installation
pip3 --version > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]]; then
    echo 'pip3 not present. Installing..'
    install_pip
fi

pip3 --version > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]]; then
    echo "Failed to install pip"
    exit 1
fi

## Update AWS CLI to  latest version
update_aws_cli

## Install library
# build_lib_wheel
# install_lib_wheel

## Install kubectl (latest 1.27 version)
kubectl version --client > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]]; then
  echo 'kubectl not present. Installing..'
  install_kubectl
fi

kubectl version --client > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]]; then
    echo "Failed to install kubectl"
    exit 1
fi

## Install eksctl
eksctl version > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]]; then
  echo 'eksctl not present. Installing..'
  install_eksctl
fi

eksctl version > /dev/null 2>&1
error_code=${?}
if [[ $error_code -ne 0 ]]; then
  echo "Failed to install eksctl"
  exit 1
fi
