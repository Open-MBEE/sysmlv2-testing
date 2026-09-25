package UsageEnd {
  private import Lib::*;

  part a : Foo { :>> name = "a"; }
  part b : Foo { :>> name = "b"; }

  connection l : Link {
    end :>> source = a;
    end :>> target = b;
  }
}
