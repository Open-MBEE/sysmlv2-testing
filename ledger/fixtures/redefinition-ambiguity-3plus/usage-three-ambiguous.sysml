package UsageThree {
  private import Lib::*;

  part a : Item { :>> name = "a"; }
  part b : Item { :>> name = "b"; }
  part c2 : Item { :>> name = "c"; }

  part d : Container {
    ref :>> items = a;
    ref :>> items = b;
    ref :>> items = c2;
  }
}
