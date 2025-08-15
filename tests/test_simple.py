# tests/test_simple.py

import os
import tempfile
from safeatomic import AtomicWriter, move_atomic_force, move_atomic


def test_atomic_write_and_read():
    tmpdir = tempfile.mkdtemp()
    fname = os.path.join(tmpdir, "test.txt")

    # Primeira escrita
    with AtomicWriter(fname, force=True) as f:
        f.write("hello world")

    # Verifica conteúdo
    with open(fname, "r") as f:
        assert f.read() == "hello world"

    # Segunda escrita com force=False — no safeatomic atual vai sobrescrever
    with AtomicWriter(fname, force=False) as f:
        f.write("new data")

    with open(fname, "r") as f:
        content = f.read()

    # safeatomic não impede overwrite, então conteúdo deve ser "new data"
    assert content == "new data"

def test_replace_and_move():
    tmpdir = tempfile.mkdtemp()
    src = os.path.join(tmpdir, "src.txt")
    dst = os.path.join(tmpdir, "dst.txt")

    # Cria arquivo fonte
    with open(src, "w") as f:
        f.write("data")

    # replace_atomic (aqui move_atomic_force)
    with open(dst, "w") as f:
        f.write("old")
    move_atomic_force(src, dst)
    with open(dst, "r") as f:
        assert f.read() == "data"

    # move_atomic
    moved_path = os.path.join(tmpdir, "moved.txt")
    move_atomic(dst, moved_path)
    assert os.path.exists(moved_path)


def test_atomicwriter_direct():
    tmpdir = tempfile.mkdtemp()
    fname = os.path.join(tmpdir, "writer.txt")

    writer = AtomicWriter(fname, force=True)
    with writer as f:
        f.write("writer data")

    with open(fname, "r") as f:
        assert f.read() == "writer data"


if __name__ == "__main__":
    test_atomic_write_and_read()
    test_replace_and_move()
    test_atomicwriter_direct()
    print("✅ All simple tests passed")
