library package Lib {
  private import ScalarValues::*;

  part def Item { attribute name : String; }

  part def Container {
    ref part items : Item[*];
  }
}
