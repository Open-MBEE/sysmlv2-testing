package UsageBare {
  private import Lib::*;

  part a : Foo { :>> name = "a"; }
  part b : Foo { :>> name = "b"; }

  connection l : Link {
    :>> source = a;
    :>> target = b;
  }
}
