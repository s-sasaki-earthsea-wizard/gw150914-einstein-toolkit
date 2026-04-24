# GW150914 Einstein Toolkit ビルドイメージ
# =================================================================
# 公式 jupyter-et リポジトリの tutorial-server/base.docker を踏襲し、
# Kruskal release (ET_2025_05) を Ubuntu 20.04 上にソースからビルドする。
#
# 公式リポジトリ: https://github.com/einsteintoolkit/jupyter-et
# 公式リリース  : https://einsteintoolkit.org/download.html
#
# 想定:
#   - 初回ビルド時間 : 60〜120 分（AMReX / ADIOS2 等の追加ライブラリ込み）
#   - 最終イメージサイズ: 5〜8 GB
#   - 再ビルド (キャッシュ有効): 10〜20 分
#
# Ubuntu 20.04 を採用する理由は公式準拠。新しい glibc を持つ Ubuntu でも
# 動くが、20.04 (g++-10) は Singularity 経由で旧型クラスタへ持ち出せる
# 互換性が確保される、という公式判断を引き継ぐ。

FROM ubuntu:20.04

USER root
ENV DEBIAN_FRONTEND=noninteractive

# ============================================================
# バージョン固定 (リリース更新時にのみ変更)
# ============================================================
# Einstein Toolkit Kruskal release
ARG ET_RELEASE=ET_2025_05
ENV ET_RELEASE=${ET_RELEASE}
# Kuibit (波形解析用 Python ライブラリ)
ARG KUIBIT_RELEASE=1.5.0
ENV KUIBIT_RELEASE=${KUIBIT_RELEASE}
# 公式準拠の Python バージョン
ENV PYVER=3.8

# ============================================================
# ホスト UID/GID (ボリュームマウント時のパーミッション一致用)
# build 時に --build-arg USER_UID=$(id -u) USER_GID=$(id -g) で上書き可能
# ============================================================
ARG USER_UID=1000
ARG USER_GID=1000

# ============================================================
# システム依存パッケージ (公式 base.docker と同一構成)
# MPI 実装は MPICH を採用 (公式 jupyter-et 準拠)
# ============================================================
RUN apt-get -qq update && \
    apt-get -qq install --no-install-recommends \
        locales locales-all \
        g++-10 gfortran-10 \
        python python3-pip python3-setuptools \
        libpython${PYVER}-dev libpython${PYVER}-dbg libpython3-dev \
        make cmake git m4 patch subversion mercurial \
        wget curl rsync unzip file pkg-config \
        gnuplot gnuplot-x11 time procps gdb \
        vim nano emacs openssh-client \
        libmpich-dev libhdf5-mpich-dev mpich \
        libscalapack-mpich-dev libscalapack-mpi-dev \
        libhdf5-dev hdf5-tools \
        gsl-bin libgsl-dev libgsl0-dev \
        libopenblas-dev liblapack-dev fftw3-dev \
        libpapi-dev libnuma-dev numactl \
        hwloc libhwloc-dev libudev-dev python3-pyudev libssl-dev \
        libmkl-dev libboost-dev libboost-all-dev \
        ffmpeg imagemagick && \
    apt-get -qq clean && \
    apt-get -qq autoclean && \
    apt-get -qq autoremove && \
    rm -rf /var/lib/apt/lists/*

# g++ / gfortran のデフォルトを 10 に固定
RUN update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-10 10 && \
    update-alternatives --install /usr/bin/gfortran gfortran /usr/bin/gfortran-10 10

# ============================================================
# Python 環境 (Jupyter Lab + 解析ライブラリ)
# 公式は jupyterhub も含むが、本プロジェクトはシングルユーザー想定なので除外
# ============================================================
RUN pip3 install --no-cache-dir pip==22.2.2 && \
    pip3 install --no-cache-dir \
        jupyterlab \
        notebook \
        matplotlib \
        numpy \
        scipy \
        h5py \
        sympy \
        kuibit==${KUIBIT_RELEASE} \
        dumb-init && \
    rm -rf /root/.cache/pip*

# ============================================================
# CarpetX 系拡張ライブラリ (公式 base.docker 順序を踏襲)
# 各ライブラリは /usr/local 配下にインストールされ、
# 後段の sim build から自動的にリンクされる。
# ============================================================

# CMake 3.29.6 (AMReX が新しめの cmake を要求)
RUN mkdir -p /tmp/dist && cd /tmp/dist && \
    wget -q https://github.com/Kitware/CMake/releases/download/v3.29.6/cmake-3.29.6-linux-x86_64.tar.gz && \
    tar xzf cmake-3.29.6-linux-x86_64.tar.gz && \
    rsync -r cmake-3.29.6-linux-x86_64/ /usr/local && \
    cd / && rm -rf /tmp/dist

# ADIOS2 2.10.2 (並列I/O、HDF5 と並ぶ I/O バックエンド)
RUN mkdir -p /tmp/src && cd /tmp/src && \
    wget -q https://github.com/ornladios/ADIOS2/archive/refs/tags/v2.10.2.tar.gz && \
    tar xzf v2.10.2.tar.gz && cd ADIOS2-2.10.2 && \
    cmake -B build \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DBUILD_SHARED_LIBS=ON \
        -DBUILD_TESTING=OFF \
        -DADIOS2_BUILD_EXAMPLES=OFF \
        -DADIOS2_USE_Fortran=OFF \
        -DADIOS2_USE_HDF5=ON && \
    cmake --build build -j$(nproc) && \
    cmake --install build && \
    cd / && rm -rf /tmp/src

# NSIMD 3.0.1 (SIMD ベクトル化、x86_64 SSE2 ターゲット)
RUN mkdir -p /tmp/src && cd /tmp/src && \
    wget -q https://github.com/agenium-scale/nsimd/archive/refs/tags/v3.0.1.tar.gz && \
    tar xzf v3.0.1.tar.gz && cd nsimd-3.0.1 && mkdir build && cd build && \
    cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo \
          -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
          -Dsimd=SSE2 -DCMAKE_INSTALL_PREFIX=/usr/local .. && \
    make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/src

# openPMD-api 0.15.1 (AMR データレイアウト標準、ADIOS2 に依存)
RUN mkdir -p /tmp/src && cd /tmp/src && \
    wget -q https://github.com/openPMD/openPMD-api/archive/refs/tags/0.15.1.tar.gz && \
    tar xzf 0.15.1.tar.gz && cd openPMD-api-0.15.1 && mkdir build && cd build && \
    cmake -DopenPMD_USE_PYTHON=python .. && \
    make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/src

# ssht 1.5.1 (スピン荷重球面調和関数)
RUN mkdir -p /tmp/src && cd /tmp/src && \
    wget -q https://github.com/astro-informatics/ssht/archive/v1.5.1.tar.gz && \
    tar xzf v1.5.1.tar.gz && cd ssht-1.5.1 && mkdir build && cd build && \
    cmake .. && make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/src

# Silo 4.11 (可視化用フォーマット)
RUN mkdir -p /tmp/src && cd /tmp/src && \
    wget -q https://github.com/LLNL/Silo/releases/download/v4.11/silo-4.11.tar.gz && \
    tar xzf silo-4.11.tar.gz && cd silo-4.11 && mkdir build && cd build && \
    ../configure \
        --disable-fortran --enable-optimization \
        --with-hdf5=/usr/lib/x86_64-linux-gnu/hdf5/serial/include,/usr/lib/x86_64-linux-gnu/hdf5/serial/lib \
        --prefix=/usr/local && \
    make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/src

# yaml-cpp 0.6.3
RUN mkdir -p /tmp/src && cd /tmp/src && \
    wget -q https://github.com/jbeder/yaml-cpp/archive/yaml-cpp-0.6.3.tar.gz && \
    tar xzf yaml-cpp-0.6.3.tar.gz && cd yaml-cpp-yaml-cpp-0.6.3 && mkdir build && cd build && \
    cmake .. && make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/src

# AMReX 23.05 (適応的メッシュリファインメント、CarpetX 用)
ARG REAL_PRECISION=real64
RUN mkdir -p /tmp/src && cd /tmp/src && \
    wget -q https://github.com/AMReX-Codes/amrex/archive/23.05.tar.gz && \
    tar xzf 23.05.tar.gz && cd amrex-23.05 && mkdir build && cd build && \
    case "${REAL_PRECISION}" in \
        real32) AMREX_PREC=SINGLE ;; \
        real64) AMREX_PREC=DOUBLE ;; \
        *) echo "Invalid REAL_PRECISION: ${REAL_PRECISION}" >&2 && exit 1 ;; \
    esac && \
    cmake -DAMReX_OMP=ON \
          -DAMReX_PARTICLES=ON \
          -DAMReX_PRECISION="$AMREX_PREC" \
          -DBUILD_SHARED_LIBS=ON \
          -DCMAKE_BUILD_TYPE=RelWithDebInfo \
          -DCMAKE_INSTALL_PREFIX=/usr/local .. && \
    make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/src

# /usr/local 配下の .so をローダキャッシュへ
RUN ldconfig

# ============================================================
# 非 root ユーザー (etuser) 作成
# ホスト UID/GID と一致させてバインドマウント時のパーミッションを揃える
# ============================================================
RUN groupadd -g ${USER_GID} etuser && \
    useradd -m -u ${USER_UID} -g ${USER_GID} -s /bin/bash etuser && \
    mkdir -p /home/etuser/work /home/etuser/simulations && \
    chown -R etuser:etuser /home/etuser

USER etuser
# Docker の USER ディレクティブは UID 切り替えのみで、$USER / $HOME は未設定のまま。
# Cactus の Formaline thorn は内部で git commit を行うため、これらが空だと
# `fatal: empty ident name (for <@localhost>) not allowed` で失敗する。
# 公式 build-cactus-tarball.sh と同等の対応。
ENV USER=etuser HOME=/home/etuser
WORKDIR /home/etuser

# Formaline thorn が要求する git の identity を設定。
# 値はビルド内部でのみ使われ、コミット先リポジトリは作られない。
RUN git config --global user.name  "Einstein Toolkit Builder" && \
    git config --global user.email "etuser@gw150914-et.local"

# ============================================================
# Einstein Toolkit (Kruskal) ソース取得とビルド
# ============================================================
# GetComponents で全 thorn (TwoPunctures, McLachlan, Carpet, AHFinderDirect 等)
# をチェックアウト。--parallel で並列ダウンロード。
RUN curl -kLO https://raw.githubusercontent.com/gridaphobe/CRL/${ET_RELEASE}/GetComponents && \
    chmod +x GetComponents && \
    ./GetComponents --parallel \
        https://bitbucket.org/einsteintoolkit/manifest/raw/${ET_RELEASE}/einsteintoolkit.th

# SimFactory のセットアップ (環境を自動検出して machine ini を生成)
WORKDIR /home/etuser/Cactus
RUN ./simfactory/bin/sim setup-silent

# ビルドオプションファイルをコピー (公式 tutorial.cfg 相当)
COPY --chown=etuser:etuser docker/cactus.cfg /home/etuser/Cactus/docker.cfg

# Cactus ビルド本体 (最も時間がかかる工程: 30〜60 分)
# MAKE_PARALLEL は -j フラグ。メモリ不足で gcc が OOM kill されるなら下げる。
ENV LD_LIBRARY_PATH=/usr/local/lib:/lib/x86_64-linux-gnu
ARG MAKE_PARALLEL=8
RUN ./simfactory/bin/sim build \
        -j${MAKE_PARALLEL} \
        --thornlist ../einsteintoolkit.th \
        --optionlist docker.cfg && \
    ls -la ./exe/cactus_sim

# ============================================================
# システム MPI のデフォルトを MPICH に固定
# ============================================================
# Ubuntu の libscalapack-mpi-dev パッケージが Open MPI を依存に引き込み、
# update-alternatives のデフォルトが OpenMPI 側に向く。
# HDF5 (libhdf5-mpich-dev) や ADIOS2 は MPICH ABI でビルドされているため、
# 実行時には mpirun.mpich (MPICH) を使う必要がある。
# ここで update-alternatives を明示的に MPICH に切替えて、
# 利用者が `mpirun` (シンボリックリンク) を使っても MPICH が呼ばれるようにする。
USER root
RUN update-alternatives --set mpi    /usr/bin/mpicc.mpich && \
    update-alternatives --set mpirun /usr/bin/mpirun.mpich

USER etuser

# ============================================================
# 起動設定
# ============================================================
WORKDIR /home/etuser/work

EXPOSE 8888

# デフォルトコマンド: Jupyter Lab をフォアグラウンドで起動
# アクセス URL (トークン付き) は `make docker-token` で取得
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser"]
