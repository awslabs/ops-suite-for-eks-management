echo "Starting lambda layer package and build"

setup_py_file=src/orchestrator/lambdas/layer/setup.py
setup_cfg_file=src/orchestrator/lambdas/layer/setup.cfg
temp=src/orchestrator/lambdas/layer/.tmp
dist=./dist/layer

echo "Uninstall already installed layer package"
pip3 uninstall eks_lambdalayer --yes
pip3

echo "Create necessary setup files for building"
echo "Removing any existing setup files"

rm -f "$setup_py_file" && rm -f "$setup_cfg_file"

touch "$setup_py_file"
cat >> "$setup_py_file"<< EOF
from setuptools import setup

setup(
    name='eks-lambdalayer',
    version='1.0.0',
    description='Lambda Layer for EKS Management Lambda functions.',
    py_modules=[
        'cluster',
        'target',
        'dynamodb',
        'event',
        'athena',
        'factory',
        'ssmautomation',
        'queries',
        'athena',
        'utils'
    ],
    package_dir={'': 'python'}
)
EOF
echo "Created $setup_py_file"

touch "$setup_cfg_file"
cat >> "$setup_cfg_file" << EOF
[build]
build_base = .tmp/build

[egg_info]
egg_base = .tmp
EOF
echo "Created $setup_cfg_file"

echo "Build the wheel"
mkdir -p "$temp" && python3 -m build  src/orchestrator/lambdas/layer --outdir "$dist"

echo "Install the wheel"
pip install -f "$dist" eks_lambdalayer

echo "Delete temp files and directory created"
rm -rf "$temp" && rm -rf "$dist" && rm "$setup_py_file" && rm "$setup_cfg_file"

echo "Installing lambda layer complete"

echo "--------------------------------------------------------------------"

echo "Starting scripts lib package and build"

wf_temp=src/orchestrator/scripts/lib/.tmp
dist=./dist/workflow

echo "Uninstalling scripts library from local"
pip3 uninstall eks_workflow --yes

echo "Build the wheel"
mkdir -p "$wf_temp" && python3 -m build  src/orchestrator/scripts/lib --outdir "$dist"

echo "Install the wheel"
pip install -f "$dist" eks_workflow

echo "Delete temp files and directory created"
rm -rf "$wf_temp" && rm -rf "$dist" rm -rf dist

echo "Installing scripts lib complete"
