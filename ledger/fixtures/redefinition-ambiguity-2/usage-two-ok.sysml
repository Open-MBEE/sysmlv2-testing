package UsageTwo {
  private import Lib::*;

  part a : Item { :>> name = "a"; }
  part b : Item { :>> name = "b"; }

  part c : Container {
    ref :>> items = a;
    ref :>> items = b;
  }
}
