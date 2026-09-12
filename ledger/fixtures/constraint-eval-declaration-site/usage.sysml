package Usage {
    private import Lib::*;
    part a : Foo { :>> controlled = true; }
    part b : Foo { :>> controlled = false; }
    connection l : Link { end :>> source = a; end :>> target = b; }
}
