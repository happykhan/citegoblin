# Install CiteGoblin

Requires Python 3.11+, Git, Node.js and npm. The commands below are for macOS/Linux; on Windows activate the environment with `.venv\Scripts\activate` instead.

```sh
git clone https://github.com/happykhan/citegoblin.git
cd citegoblin
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[google]'
citegoblin setup-formatter
```
